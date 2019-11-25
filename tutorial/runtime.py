import asyncio
import functools
import logging
import pickle
import time
from abc import ABC
from asyncio.futures import Future

from tutorial.asyncoro import VariableExchanger


class Party:
    """Information about a party in the MPC protocol."""

    def __init__(self, pid, host=None, port=None):
        """Initialize a party with given party identity pid."""
        self.pid = pid
        self.host = host
        self.port = port
        self.protocol = None

    def __repr__(self):
        """String representation of the party."""
        if self.host is None:
            return '<Party {}>'.format(self.pid)

        return '<Party {}: {}:{}>'.format(self.pid, self.host, self.port)

    def send(self, var):
        assert var.done(), "Variable {} has to be feed first".format(var.name)
        b = pickle.dumps(var.result())
        self.protocol.send_data(var.pc, b)

    def receive(self, var):
        if var.pc in self.protocol.buffer:
            payload = self.protocol.buffer[var.pc]
            data = pickle.loads(payload)
            if data is not None:
                var.set_result(data)
            else:
                logging.debug('not a variable')
        else:
            fut = Future(loop=var.runtime.loop)
            self.protocol.buffer[var.pc] = fut

            def when_finished(_fut):
                d = _fut.result()
                d = pickle.loads(d)
                if d is not None and not var.done():
                    var.set_result(d)

            fut.add_done_callback(when_finished)


def to_future(func):

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        name = '{}('.format(func.__name__)
        name += ','.join(repr(a) for a in args)
        name += ','.join('{}_{}'.format(k, v) for k, v in kwargs.items()) + ')'

        d = self.loop.create_task(func(self, *args, **kwargs))
        v = Op(self, name=name)
        d.add_done_callback(lambda x: v.set_result(x.result()))
        return v

    return wrapper


async def handle_awaitable(this):
    if asyncio.iscoroutine(this) or asyncio.isfuture(this):
        this = await this
    return this


class Runtime:

    def __init__(self, pid, parties, *args):
        self.pid = pid
        self.parties = parties
        self.variables = set()
        self.loop = asyncio.get_event_loop()
        self._pc = 0

    @property
    def pc(self):
        pc = self._pc
        self._pc += 1
        return pc

    @property
    def protocol(self):
        return self.parties[self.pid].protocol

    @protocol.setter
    def protocol(self, protocol):
        self.parties[self.pid].protocol = protocol

    @property
    def port(self):
        return self.parties[self.pid].port

    async def start(self):
        server = None
        self.protocol = Future(loop=self.loop)
        loop = asyncio.get_event_loop()

        # Creating the server
        if self.pid:
            factory = lambda: VariableExchanger(self)
            server = await loop.create_server(factory, port=self.port)
            logging.debug(f'Listening on port {self.port}')

        # Setting up a connection with all those who have
        for peer in self.parties[self.pid + 1:]:
            while True:
                try:
                    factory = lambda: VariableExchanger(self, peer.pid)
                    await loop.create_connection(factory, peer.host, peer.port)
                    logging.debug(f'Connected to {peer.host}:{peer.port}')
                    break
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logging.debug(exc)
                time.sleep(0.1)

        # Waiting until all the parties are connected
        await self.protocol

        logging.debug('Connected')

        # Server is closed immediately after the connections are set up
        if server:
            server.close()

    async def shutdown(self):
        """Shutdown all the connections"""
        for peer in self.parties:
            if peer.pid != self.pid:
                peer.protocol.close_connection()

    def run(self, f):
        """Run the given coroutine or future until it is done."""
        return self.loop.run_until_complete(f)

    async def __aenter__(self):
        """Start runtime when entering async with context."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Shutdown runtime when exiting async with context."""
        await self.shutdown()

    @to_future
    async def add(self, this, other):
        a = await handle_awaitable(this)
        b = await handle_awaitable(other)

        return a + b

    @to_future
    async def mul(self, this, other):
        a = await handle_awaitable(this)
        b = await handle_awaitable(other)

        return a * b

    @to_future
    async def pow(self, this, other):
        a = await handle_awaitable(this)
        b = await handle_awaitable(other)

        return a ** b

    def variable(self, name=None):
        i = len(self.variables)
        if name is None:
            name = 'var_{}'.format(i)

        var = Variable(self, name=name)
        self.variables.add(var)
        return var

    async def feed(self, names):
        for k, v in names.items():
            if k not in self.variables:
                raise Exception('Variable {} does not exist'.format(k))
            k.set_result(v)

        for var in names.keys():
            for party in self.parties:
                if party.pid != self.pid:
                    logging.debug(f'{party}.send({var})')
                    party.send(var)

        variables = set(self.variables).difference(names.keys())
        for var in variables:
            for party in self.parties:
                if party.pid != self.pid:
                    logging.debug(f'{party}.receive({var})')
                    party.receive(var)


class FutureWrapper(ABC, Future):

    def __init__(self, runtime, name=''):
        super(FutureWrapper, self).__init__(loop=runtime.loop)
        self.name = name
        self.runtime = runtime
        self.pc = runtime.pc

    def __repr__(self):
        return self.name

    def __add__(self, other):
        return self.runtime.add(self, other)

    def __mul__(self, other):
        return self.runtime.mul(self, other)

    def __pow__(self, other, modulo=None):
        return self.runtime.pow(self, other)


class Op(FutureWrapper):
    pass


class Variable(FutureWrapper):
    pass


import logging

import numpy as np

from tutorial import asynt


async def main():
    var1 = asynt.variable(name='var_0')
    var2 = asynt.variable(name='var_1')
    var3 = asynt.variable(name='var_2')

    add = var1 + var2
    op = add * var3
    op *= 2
    op **= 3.0

    logging.debug('Starting')

    async with asynt:
        logging.debug('Feeding')

        if asynt.pid == 0:
            v1 = np.ones((3, 1))
            asynt.feed({var1: v1})

        elif asynt.pid == 1:
            v2 = np.array([[1, 1, 1],
                           [2, 2, 2],
                           [3, 3, 3]])
            asynt.feed({var2: v2})

        elif asynt.pid == 2:
            v3 = np.array([0, 1, 2]).reshape((3, 1))
            asynt.feed({var3: v3})

        else:
            asynt.feed()

        res = await op
        print(res)

if __name__ == '__main__':
    asynt.run(main())

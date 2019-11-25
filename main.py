import logging

import numpy as np

from tutorial import dag


async def main():
    var1 = dag.variable(name='var_0')
    var2 = dag.variable(name='var_1')
    var3 = dag.variable(name='var_2')

    add = var1 + var2
    mul = add * var3
    # mul *= 2
    # mul **= 3

    logging.debug('Starting')

    async with dag:
        logging.debug('Feeding')

        if dag.pid == 0:
            v1 = np.ones((3, 1))
            await dag.feed({var1: v1})

        elif dag.pid == 1:
            v2 = np.array([[1, 1, 1],
                          [2, 2, 2],
                          [3, 3, 3]])
            await dag.feed({var2: v2})

        elif dag.pid == 2:
            v3 = np.array([0, 1, 2]).reshape((3, 1))
            print(v3)
            await dag.feed({var3: v3})
        else:
            dag.feed()

        res = await mul
        print(res)

if __name__ == '__main__':
    dag.run(main())

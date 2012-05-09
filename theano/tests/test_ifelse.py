"""
 Tests fof the lazy conditiona
"""

__docformat__ = 'restructedtext en'
__authors__ = ("Razvan Pascanu ")
__copyright__ = "(c) 2010, Universite de Montreal"
__contact__ = "Razvan Pascanu <r.pascanu@gmail>"

import unittest
import numpy
from nose.plugins.skip import SkipTest

import theano
from theano import tensor
import theano.ifelse
from theano.ifelse import IfElse, ifelse
from theano.tests  import unittest_tools as utt


class test_ifelse(unittest.TestCase, utt.TestOptimizationMixin):
    mode = None
    dtype = theano.config.floatX
    cast_output = staticmethod(tensor.as_tensor_variable)

    def get_ifelse(self, n):
        if theano.config.mode == "FAST_COMPILE":
            return IfElse(n)
        else:
            return IfElse(n, as_view=True)

    def test_lazy_if(self):
        # Tests that lazy if works .. even if the two results have different
        # shapes but the same type (i.e. both vectors, or matrices or
        # whatnot of same dtype)
        x = tensor.vector('x', dtype=self.dtype)
        y = tensor.vector('y', dtype=self.dtype)
        c = tensor.iscalar('c')
        f = theano.function([c, x, y], ifelse(c, x, y), mode=self.mode)
        self.assertFunctionContains1(f, self.get_ifelse(1))
        rng = numpy.random.RandomState(utt.fetch_seed())

        xlen = rng.randint(200)
        ylen = rng.randint(200)

        vx = numpy.asarray(rng.uniform(size=(xlen,)), self.dtype)
        vy = numpy.asarray(rng.uniform(size=(ylen,)), self.dtype)

        assert numpy.allclose(vx, f(1, vx, vy))
        assert numpy.allclose(vy, f(0, vx, vy))

    def test_lazy_if_on_generics(self):
        x = theano.generic()
        y = theano.generic()
        c = tensor.iscalar('c')
        f = theano.function([c, x, y], ifelse(c, x, y))

        vx = ['testX']
        vy = ['testY']
        assert f(1, vx, vy) == vx
        assert f(0, vx, vy) == vy

    def test_grad_lazy_if(self):
        # Tests that we can compute the gradients through lazy if
        x = tensor.vector('x', dtype=self.dtype)
        y = tensor.vector('y', dtype=self.dtype)
        c = tensor.iscalar('c')
        z = ifelse(c, x, y)
        gx, gy = tensor.grad(z.sum(), [x, y])

        f = theano.function([c, x, y], [self.cast_output(gx),
                                        self.cast_output(gy)],
                            mode=self.mode)
        # There is only 2 of the 3 ifelse that are moved on the GPU.
        # The one that stay on the CPU is for the shape.
        self.assertFunctionContains(f, self.get_ifelse(1), min=2, max=3)
        rng = numpy.random.RandomState(utt.fetch_seed())

        xlen = rng.randint(200)
        ylen = rng.randint(200)

        vx = numpy.asarray(rng.uniform(size=(xlen,)), self.dtype)
        vy = numpy.asarray(rng.uniform(size=(ylen,)), self.dtype)
        gx0, gy0 = f(1, vx, vy)
        assert numpy.allclose(gx0.shape, vx.shape)
        assert numpy.allclose(gy0.shape, vy.shape)
        assert numpy.all(numpy.asarray(gx0) == 1.)
        assert numpy.all(numpy.asarray(gy0) == 0.)

        gx0, gy0 = f(0, vx, vy)
        assert numpy.allclose(gx0.shape, vx.shape)
        assert numpy.allclose(gy0.shape, vy.shape)
        assert numpy.all(numpy.asarray(gx0) == 0.)
        assert numpy.all(numpy.asarray(gy0) == 1.)

    def test_multiple_out(self):
        x1 = tensor.vector('x1', dtype=self.dtype)
        x2 = tensor.vector('x2', dtype=self.dtype)
        y1 = tensor.vector('y1', dtype=self.dtype)
        y2 = tensor.vector('y2', dtype=self.dtype)
        c = tensor.iscalar('c')
        z = ifelse(c, (x1, x2), (y1, y2))
        f = theano.function([c, x1, x2, y1, y2], z, mode=self.mode)
        self.assertFunctionContains1(f, self.get_ifelse(2))

        ifnode = [x for x in f.maker.env.toposort()
                  if isinstance(x.op, IfElse)][0]
        assert len(ifnode.outputs) == 2

        rng = numpy.random.RandomState(utt.fetch_seed())

        x1len = rng.randint(200)
        x2len = rng.randint(200)
        y1len = rng.randint(200)
        y2len = rng.randint(200)

        vx1 = numpy.asarray(rng.uniform(size=(x1len,)), self.dtype)
        vx2 = numpy.asarray(rng.uniform(size=(x2len,)), self.dtype)
        vy1 = numpy.asarray(rng.uniform(size=(y1len,)), self.dtype)
        vy2 = numpy.asarray(rng.uniform(size=(y2len,)), self.dtype)

        ovx1, ovx2 = f(1, vx1, vx2, vy1, vy2)
        ovy1, ovy2 = f(0, vx1, vx2, vy1, vy2)
        assert numpy.allclose(vx1, ovx1)
        assert numpy.allclose(vy1, ovy1)
        assert numpy.allclose(vx2, ovx2)
        assert numpy.allclose(vy2, ovy2)

    def test_multiple_out_grad(self):
        # Tests that we can compute the gradients through lazy if
        x1 = tensor.vector('x1')
        x2 = tensor.vector('x2')
        y1 = tensor.vector('y1')
        y2 = tensor.vector('y2')
        c = tensor.iscalar('c')
        z = ifelse(c, (x1, x2), (y1, y2))
        grads = tensor.grad(z[0].sum() + z[1].sum(),
                            [x1, x2, y1, y2])

        f = theano.function([c, x1, x2, y1, y2], grads)
        rng = numpy.random.RandomState(utt.fetch_seed())

        lens = [rng.randint(200) for i in range(4)]
        values = [numpy.asarray(rng.uniform(size=(l,)), theano.config.floatX)
                  for l in lens]
        outs_1 = f(1, *values)
        assert all([x.shape[0] == y for x, y in zip(outs_1, lens)])
        assert numpy.all(outs_1[0] == 1.)
        assert numpy.all(outs_1[1] == 1.)
        assert numpy.all(outs_1[2] == 0.)
        assert numpy.all(outs_1[3] == 0.)

        outs_0 = f(0, *values)
        assert all([x.shape[0] == y for x, y in zip(outs_1, lens)])
        assert numpy.all(outs_0[0] == 0.)
        assert numpy.all(outs_0[1] == 0.)
        assert numpy.all(outs_0[2] == 1.)
        assert numpy.all(outs_0[3] == 1.)

    def test_merge(self):
        raise SkipTest("Optimization temporarily disabled")
        x = tensor.vector('x')
        y = tensor.vector('y')
        c = tensor.iscalar('c')
        z1 = ifelse(c, x + 1, y + 1)
        z2 = ifelse(c, x + 2, y + 2)
        z = z1 + z2
        f = theano.function([c, x, y], z)
        assert len([x for x in f.maker.env.toposort()
                    if isinstance(x.op, IfElse)]) == 1

    def test_remove_useless_inputs1(self):
        raise SkipTest("Optimization temporarily disabled")
        x = tensor.vector('x')
        y = tensor.vector('y')
        c = tensor.iscalar('c')
        z = ifelse(c, (x, x), (y, y))
        f = theano.function([c, x, y], z)

        ifnode = [x for x in f.maker.env.toposort()
                  if isinstance(x.op, IfElse)][0]
        assert len(ifnode.inputs) == 3

    def test_remove_useless_inputs2(self):
        raise SkipTest("Optimization temporarily disabled")
        x1 = tensor.vector('x1')
        x2 = tensor.vector('x2')
        y1 = tensor.vector('y1')
        y2 = tensor.vector('y2')
        c = tensor.iscalar('c')
        z = ifelse(c, (x1, x1, x1, x2, x2), (y1, y1, y2, y2, y2))
        f = theano.function([c, x1, x2, y1, y2], z)

        ifnode = [x for x in f.maker.env.toposort()
                  if isinstance(x.op, IfElse)][0]
        assert len(ifnode.outputs) == 3

    def test_pushout1(self):
        raise SkipTest("Optimization temporarily disabled")
        x1 = tensor.scalar('x1')
        x2 = tensor.scalar('x2')
        y1 = tensor.scalar('y1')
        y2 = tensor.scalar('y2')
        w1 = tensor.scalar('w1')
        w2 = tensor.scalar('w2')
        c = tensor.iscalar('c')
        x, y = ifelse(c, (x1, y1), (x2, y2), name='f1')
        z = ifelse(c, w1, w2, name='f2')
        out = x * z * y

        f = theano.function([x1, x2, y1, y2, w1, w2, c], out,
                            allow_input_downcast=True)
        assert isinstance(f.maker.env.toposort()[-1].op, IfElse)
        rng = numpy.random.RandomState(utt.fetch_seed())
        vx1 = rng.uniform()
        vx2 = rng.uniform()
        vy1 = rng.uniform()
        vy2 = rng.uniform()
        vw1 = rng.uniform()
        vw2 = rng.uniform()

        assert numpy.allclose(f(vx1, vx2, vy1, vy2, vw1, vw2, 1),
                              vx1 * vy1 * vw1)
        assert numpy.allclose(f(vx1, vx2, vy1, vy2, vw1, vw2, 0),
                              vx2 * vy2 * vw2)

    def test_pushout3(self):
        raise SkipTest("Optimization temporarily disabled")
        x1 = tensor.scalar('x1')
        y1 = tensor.scalar('x2')
        y2 = tensor.scalar('y2')
        c = tensor.iscalar('c')
        two = numpy.asarray(2, dtype=theano.config.floatX)
        x, y = ifelse(c, (x1, y1), (two, y2), name='f1')
        o3 = numpy.asarray(0.3, dtype=theano.config.floatX)
        o2 = numpy.asarray(0.2, dtype=theano.config.floatX)
        z = ifelse(c, o3, o2, name='f2')
        out = x * z * y

        f = theano.function([x1, y1, y2, c], out,
                            allow_input_downcast=True)
        assert isinstance(f.maker.env.toposort()[-1].op, IfElse)
        rng = numpy.random.RandomState(utt.fetch_seed())
        vx1 = rng.uniform()
        vy1 = rng.uniform()
        vy2 = rng.uniform()

        assert numpy.allclose(f(vx1, vy1, vy2, 1), vx1 * vy1 * 0.3)
        assert numpy.allclose(f(vx1, vy1, vy2, 0), 2 * vy2 * 0.2)

    def test_pushout2(self):
        raise SkipTest("Optimization temporarily disabled")
        x1 = tensor.scalar('x1')
        x2 = tensor.scalar('x2')
        y1 = tensor.scalar('y1')
        y2 = tensor.scalar('y2')
        w1 = tensor.scalar('w1')
        w2 = tensor.scalar('w2')
        c = tensor.iscalar('c')
        x, y = ifelse(c, (x1, y1), (x2, y2), name='f1')
        z = ifelse(x > y, w1, w2, name='f2')
        out = x * z * y

        f = theano.function([x1, x2, y1, y2, w1, w2, c], out,
                            allow_input_downcast=True)
        assert isinstance(f.maker.env.toposort()[-1].op, IfElse)
        rng = numpy.random.RandomState(utt.fetch_seed())
        vx1 = rng.uniform()
        vx2 = rng.uniform()
        vy1 = rng.uniform()
        vy2 = rng.uniform()
        vw1 = rng.uniform()
        vw2 = rng.uniform()
        if vx1 > vy1:
            vw = vw1
        else:
            vw = vw2
        assert numpy.allclose(f(vx1, vx2, vy1, vy2, vw1, vw2, 1),
                              vx1 * vy1 * vw)

        if vx2 > vy2:
            vw = vw1
        else:
            vw = vw2
        assert numpy.allclose(f(vx1, vx2, vy1, vy2, vw1, vw2, 0),
                              vx2 * vy2 * vw)

    def test_merge_ifs_true_false(self):
        raise SkipTest("Optimization temporarily disabled")
        x1 = tensor.scalar('x1')
        x2 = tensor.scalar('x2')
        y1 = tensor.scalar('y1')
        y2 = tensor.scalar('y2')
        w1 = tensor.scalar('w1')
        w2 = tensor.scalar('w2')
        c = tensor.iscalar('c')

        out = ifelse(c,
            ifelse(c, x1, x2) + ifelse(c, y1, y2) + w1,
            ifelse(c, x1, x2) + ifelse(c, y1, y2) + w2)
        f = theano.function([x1, x2, y1, y2, w1, w2, c], out,
                            allow_input_downcast=True)
        assert len([x for x in f.maker.env.toposort()
                if isinstance(x.op, IfElse)]) == 1

        rng = numpy.random.RandomState(utt.fetch_seed())
        vx1 = rng.uniform()
        vx2 = rng.uniform()
        vy1 = rng.uniform()
        vy2 = rng.uniform()
        vw1 = rng.uniform()
        vw2 = rng.uniform()
        assert numpy.allclose(f(vx1, vx2, vy1, vy2, vw1, vw2, 1),
                              vx1 + vy1 + vw1)
        assert numpy.allclose(f(vx1, vx2, vy1, vy2, vw1, vw2, 0),
                              vx2 + vy2 + vw2)


if __name__ == '__main__':
    print ' Use nosetests to run these tests '

import math
import random
import unittest
import torch
import torch.legacy.nn as nn

PRECISION = 1e-5
EXP_PRECISION = 1e-4

class TestCaseBase(object):
    def __init__(self, constructor, constructor_args=tuple(), input_size=None,
            input=None, desc='', reference_fn=None):
        if input_size is None and input is None:
            raise RuntimeError("Specify either an input tensor, or it's size!")
        self.constructor = constructor
        self.constructor_args = constructor_args
        self.input = input
        self.input_size = input_size
        self.desc = desc
        self.reference_fn = reference_fn

    def _get_input(self):
        if self.input is not None:
            return self.input

        def map_input_sizes(sizes):
            if isinstance(sizes, list):
                return [map_input_sizes(s) for s in sizes]
            else:
                return torch.randn(*sizes)

        assert self.input_size is not None
        return map_input_sizes(self.input_size)

    def __call__(self, test_case):
        raise NotImplementedError


class SimpleTestCase(TestCaseBase):
    def __init__(self, *args, check_inplace=False, jacobian_input=True, **kwargs):
        super(SimpleTestCase, self).__init__(*args, **kwargs)
        self.check_inplace = check_inplace
        self.jacobian_input = jacobian_input

    def __call__(self, test_case):
        module = self.constructor(*self.constructor_args)
        input = self._get_input()

        if self.reference_fn is not None:
            out = module.forward(input)
            expected_out = self.reference_fn(module, test_case._clone_input(input))
            test_case.assertEqual(out, expected_out)

        # TODO: check update parameters
        # TODO: test IO
        module.training()
        test_case.check_jacobian(module, input, self.jacobian_input)
        module.evaluate()
        test_case.check_jacobian(module, input, self.jacobian_input)

        if self.check_inplace:
            input2 = test_case._clone_input(input)
            module_ip = self.constructor(*self.constructor_args, inplace=True)
            output = module.forward(input)
            test_case.assertEqual(input, input2)
            output2 = module_ip.forward(input2)
            test_case.assertNotEqual(input, input2)
            test_case.assertEqual(output, input2)


class CriterionTestCase(TestCaseBase):
    def __init__(self, *args, target=None, **kwargs):
        super(CriterionTestCase, self).__init__(*args, **kwargs)
        self.target = target

    def __call__(self, test_case):
        module = self.constructor(*self.constructor_args)
        input = self._get_input()

        test_case.check_criterion_jacobian(module, input, self.target)

        if self.reference_fn is not None:
            out = module.forward(input, self.target)
            expected_out = self.reference_fn(module, test_case._clone_input(input),
                    test_case._clone_input(self.target))
            test_case.assertEqual(out, expected_out)


simple_tests = [
    SimpleTestCase(nn.Add,
                    (torch.LongStorage([5, 4]),),
                    input_size=(3, 5, 4),
                    desc='3D'),
    SimpleTestCase(nn.Add,
                    (1, True),
                    input_size=(3, 1, 4),
                    desc='scalar'),
    SimpleTestCase(nn.AddConstant,
                    (3.5,),
                    input_size=(3, 5, 4),
                    reference_fn=lambda _,i: i + 3.5,
                    check_inplace=True),
    SimpleTestCase(nn.CMul,
                    (5, 6),
                    input_size=(10, 5, 6),
                    desc='3D'),
    SimpleTestCase(nn.CMul,
                    (50, 4),
                    input_size=(1, 50, 4),
                    desc='3D_single_example'),
    SimpleTestCase(nn.CMul,
                    (1, 5),
                    input=torch.randn(10, 3, 5)[:,1],
                    desc='3D_noncontiguous'),
    SimpleTestCase(nn.Exp,
                    input_size=(2, 3, 4),
                    reference_fn=lambda _,i: i.exp()),
    SimpleTestCase(nn.Log,
                    input=torch.rand(2, 3, 2) + 0.1,
                    reference_fn=lambda _,i: i.log()),
    SimpleTestCase(nn.LogSigmoid,
                    input_size=(2, 3, 4),
                    reference_fn=lambda _,i: i.sigmoid().log()),
    SimpleTestCase(nn.LogSoftMax,
                    input_size=(10, 20),
                    reference_fn=lambda _,i: torch.exp(i).cdiv(torch.exp(i).sum(1).expand(10, 20)).log()),
    SimpleTestCase(nn.HardTanh,
                    input_size=(3, 2, 5),
                    reference_fn=lambda _,i: i.clamp(-1, 1)),
    SimpleTestCase(nn.Clamp,
                    (-2, 5),
                    input=torch.randn(3, 2, 50) * 6,
                    reference_fn=lambda _,i: i.clamp(-2, 5)),
    SimpleTestCase(nn.Abs,
                    input_size=(3, 20, 5),
                    reference_fn=lambda _,i: i.abs()),
    # SimpleTestCase(nn.Threshold,
                    # (2, 5),
                    # input_size=(3, 50, 5)),
    SimpleTestCase(nn.ELU,
                    (2,),
                    input_size=(3, 2, 5),
                    check_inplace=True),
    # SimpleTestCase(nn.PReLU,
                    # tuple(),
                    # input_size=(3, 2, 5)),
    # SimpleTestCase(nn.PReLU,
                    # tuple(10),
                    # input_size=(4, 10, 2, 5)),
    # SimpleTestCase(nn.RReLU,
                    # tuple(),
                    # input_size=(4, 2, 5),
                    # check_inplace=True),
    # SimpleTestCase(nn.RReLU,
                    # (0.1, 0.9),
                    # input_size=(4, 4, 5),
                    # check_inplace=True),
    # SimpleTestCase(nn.SoftShrink,
                    # tuple(),
                    # input_size=(3, 2, 5),
                    # check_inplace=True),
    # SimpleTestCase(nn.SoftShrink,
                    # (1,),
                    # input_size=(3, 2, 5),
                    # check_inplace=True),
    SimpleTestCase(nn.LeakyReLU,
                    input_size=(3, 2, 5),
                    check_inplace=True),
    SimpleTestCase(nn.LeakyReLU,
                    (0.5,),
                    input_size=(3, 2, 5),
                    check_inplace=True,
                    desc='with_negval'),
    SimpleTestCase(nn.Bilinear,
                    (2, 3, 10),
                    input_size=[(4, 2), (4, 3)]),
    SimpleTestCase(nn.Bilinear,
                    (5, 4, 2),
                    input_size=[(2, 5), (2, 4)],
                    desc='small_output'),
    SimpleTestCase(nn.Euclidean,
                    (5, 7),
                    input_size=(10, 5)),
    SimpleTestCase(nn.Cosine,
                    (5, 7),
                    input_size=(10, 5)),
    SimpleTestCase(nn.CAddTable,
                    input_size=[(5, 7), (5, 7)]),
    SimpleTestCase(nn.CSubTable,
                    input_size=[(5, 7), (5, 7)]),
    SimpleTestCase(nn.CDivTable,
                    input=[torch.randn(1, 7), torch.rand(1, 7) + 0.1]),
    SimpleTestCase(nn.CMulTable,
                    input_size=[(5, 7), (5, 7)]),
    # SimpleTestCase(nn.Power,
                    # (2,),
                    # input_size=(10, 2, 4),
                    # reference_fn=lambda _,i: i.cmul(i))
    # SimpleTestCase(nn.Power,
                    # (2.5,),
                    # input_size=(10, 2, 4)),
    # SimpleTestCase(nn.Square,
                    # tuple(),
                    # input_size=(10, 2, 4),
                    # reference_fn=lambda _,i: i.cmul(i))
    # SimpleTestCase(nn.Sqrt,
                    # tuple(),
                    # input_size=(10, 2, 4),
                    # reference_fn=lambda _,i: i.sqrt())
    SimpleTestCase(nn.BatchNormalization,
                    (10,),
                    input_size=(4, 10),
                    desc='affine'),
    SimpleTestCase(nn.BatchNormalization,
                    (10, 1e-3, 0.3, False),
                    input_size=(4, 10),
                    desc='not_affine'),
    # TODO: reference function
    SimpleTestCase(nn.HardShrink,
                    (2,),
                    input_size=(4, 3, 2, 4)),
    SimpleTestCase(lambda: nn.Sequential().add(nn.GradientReversal()).add(nn.GradientReversal()),
                    input_size=(4, 3, 2, 2)),
    SimpleTestCase(nn.Identity,
                    input_size=(4, 3, 2, 4),
                    reference_fn=lambda _,i: i),
    SimpleTestCase(nn.DotProduct,
                    input_size=[(10, 4), (10, 4)],
                    reference_fn=lambda _,i: torch.Tensor(list(
                        a.dot(b) for a, b in zip(i[0], i[1])))
                    ),
    SimpleTestCase(nn.CosineDistance,
                    input_size=[(10, 4), (10, 4)],
                    reference_fn=lambda _,i: torch.Tensor(list(
                        a.dot(b) / (a.norm(2) * b.norm(2)) for a, b in zip(i[0], i[1])))
                    ),
    SimpleTestCase(nn.JoinTable,
                    (0,),
                    input_size=[(10, 4), (10, 4)],
                    reference_fn=lambda _,i: torch.cat(i, 0),
                    desc='first_dim'),
    SimpleTestCase(nn.JoinTable,
                    (2,),
                    input_size=[(2, 4, 2), (2, 4, 2)],
                    reference_fn=lambda _,i: torch.cat(i, 2),
                    desc='positive_dim_index'),
    SimpleTestCase(nn.JoinTable,
                    (-1,),
                    input_size=[(2, 4, 2, 4), (2, 4, 2, 4)],
                    reference_fn=lambda _,i: torch.cat(i, 3),
                    desc='negative_dim_index'),
    # TODO: hessian?
    SimpleTestCase(nn.Linear,
                    (10,8),
                    input_size=(4, 10),
                    reference_fn=lambda m,i: i * m.weight.t() + m.bias.view(1, -1).expand(4, 8)),
    SimpleTestCase(nn.MM,
                    input_size=[(4, 5, 3), (4, 3, 2)],
                    reference_fn=lambda _,i: torch.bmm(*i)),
    SimpleTestCase(nn.Max,
                    input_size=(4, 5, 3),
                    reference_fn=lambda _,i: torch.max(i, 0)[0].squeeze()),
    SimpleTestCase(nn.Max,
                    (1,),
                    input_size=(4, 5, 3),
                    reference_fn=lambda _,i: torch.max(i, 1)[0].squeeze(),
                    desc='with_dimension'),
    SimpleTestCase(nn.Min,
                    input_size=(4, 5, 3),
                    reference_fn=lambda _,i: torch.min(i, 0)[0].squeeze()),
    SimpleTestCase(nn.Min,
                    (1,),
                    input_size=(4, 5, 3),
                    reference_fn=lambda _,i: torch.min(i, 1)[0].squeeze(),
                    desc='with_dimension'),
    SimpleTestCase(nn.MixtureTable,
                    tuple(),
                    input_size=[(5, 3), (5, 3, 6)]),
    # TODO: Fix index checks in THNN
    # SimpleTestCase(nn.LookupTable,
                    # (4, 3),
                    # input=(torch.randperm(2)+1).repeatTensor(1, 2),
                    # jacobian_input=False),
    SimpleTestCase(nn.Mul,
                    input_size=(2, 3, 4, 2),
                    reference_fn=lambda m,i: i * m.weight[0]),
    SimpleTestCase(nn.MulConstant,
                    (4,),
                    input_size=(2, 3, 4, 2),
                    reference_fn=lambda m,i: i * 4,
                    check_inplace=True),
    CriterionTestCase(nn.AbsCriterion,
                        input_size=(2, 3, 4),
                        target=torch.randn(2, 3, 4),
                        reference_fn=lambda _,i,t: 1/i.numel() * \
                            sum((a-b).abs().sum() for a,b in zip(i, t))
                    ),
    CriterionTestCase(nn.BCECriterion,
                        input_size=(15, 10),
                        target=torch.randn(15, 10).gt(0).double()
                    ),
    CriterionTestCase(nn.BCECriterion,
                        (torch.rand(10),),
                        input_size=(15, 10),
                        target=torch.randn(15, 10).gt(0).double(),
                        desc='weights'),
    CriterionTestCase(nn.ClassNLLCriterion,
                        input=torch.rand(15, 10).log(),
                        target=torch.Tensor(15).uniform().mul(10).ceil()),
    CriterionTestCase(nn.ClassNLLCriterion,
                        (torch.rand(10),),
                        input=torch.rand(15, 10).log(),
                        target=torch.Tensor(15).uniform().mul(10).ceil(),
                        desc='weights'),
    CriterionTestCase(nn.CrossEntropyCriterion,
                        input=torch.randn(15, 10),
                        target=torch.Tensor(15).uniform().mul(10).ceil()),
    CriterionTestCase(nn.CrossEntropyCriterion,
                        (torch.rand(10),),
                        input=torch.randn(15, 10),
                        target=torch.Tensor(15).uniform().mul(10).ceil(),
                        desc='weights'),
    CriterionTestCase(nn.CosineEmbeddingCriterion,
                        input=[torch.rand(15, 10), torch.rand(15, 10)],
                        target=torch.randn(15).sign()),
    CriterionTestCase(nn.CosineEmbeddingCriterion,
                        (0.5,),
                        input=[torch.rand(15, 10), torch.rand(15, 10)],
                        target=torch.randn(15).sign(),
                        desc='margin'),
    CriterionTestCase(nn.DistKLDivCriterion,
                        input=torch.rand(10, 10).log(),
                        target=torch.rand(10, 10)),
    CriterionTestCase(nn.HingeEmbeddingCriterion,
                        input=torch.rand(10),
                        target=torch.randn(10).gt(0).double()),
    CriterionTestCase(nn.HingeEmbeddingCriterion,
                        (0.5,),
                        input=torch.rand(10),
                        target=torch.randn(10).gt(0).double(),
                        desc='margin'),
    CriterionTestCase(nn.L1Cost,
                        input=torch.randn(2, 3, 4, 5),
                        target=None),
    CriterionTestCase(nn.L1HingeEmbeddingCriterion,
                        input=[torch.randn(2, 3, 4, 5), torch.randn(2, 3, 4, 5)],
                        target=1),
    CriterionTestCase(nn.L1HingeEmbeddingCriterion,
                        (2,),
                        input=[torch.randn(2, 3, 4, 5), torch.randn(2, 3, 4, 5)],
                        target=1,
                        desc='margin'),
    CriterionTestCase(nn.MSECriterion,
                        input=torch.randn(2, 3, 4, 5),
                        target=torch.randn(2, 3, 4, 5),
                        reference_fn=lambda _,i,t: (i-t).abs().pow(2).sum() / i.numel()),
    CriterionTestCase(nn.MarginCriterion,
                        input_size=(5, 10),
                        target=torch.randn(5, 10).sign()),
    CriterionTestCase(nn.MarginRankingCriterion,
                        input=[torch.randn(50).mul(10), torch.randn(50).mul(10)],
                        target=torch.randn(50).sign()),
    CriterionTestCase(nn.MarginRankingCriterion,
                        (2,),
                        input=[torch.randn(50).mul(10), torch.randn(50).mul(10)],
                        target=torch.randn(50).sign(),
                        desc='margin'),
    CriterionTestCase(nn.ClassSimplexCriterion,
                        (30,),
                        input=torch.randn(5, 30).mul(10).renorm(2, 0, 1),
                        target=torch.rand(5).mul(30).floor().long(),
                        desc='margin'),
]
# TODO: FlattenTable gradient
# TODO: CriterionTable
# TODO: MultiCriterion

# simple_tests.extend([
    # SimpleTestCase(nn.Normalize,
                    # (1.5,)
                    # input_size=(5, 10*p),
                    # reference_fn=lambda _,i: torch.div(i, i.norm(p)),
                    # desc=str(p)) for p in (1.5, 2, 4)])

def make_test_closure(test):
    def _tmp(self):
        test(self)
    return _tmp

def prepare_simple_tests():
    for test in simple_tests:
        test_name = 'test_' + test.constructor.__name__
        if test.desc:
            test_name += '_' + test.desc
        if hasattr(TestNN, test_name):
            raise RuntimeError('Found two tests with the same name: ' + test_name)
        setattr(TestNN, test_name, make_test_closure(test))

class TestNN(unittest.TestCase):

    # TODO: subclass Torch tests
    def assertEqual(self, x, y, prec=None, message=''):
        if prec is None:
            prec = PRECISION

        if torch.isTensor(x) and torch.isTensor(y):
            max_err = 0
            super(TestNN, self).assertEqual(x.size().tolist(), y.size().tolist())
            max_err = (x - y).abs().max()
            self.assertLessEqual(max_err, prec)
        elif isinstance(x, list) and isinstance(y, list):
            self.assertEqual(len(x), len(y))
            for _x, _y in zip(x, y):
                self.assertEqual(_x, _y)
        else:
            try:
                self.assertLessEqual(abs(x - y), prec)
            except:
                super(TestNN, self).assertEqual(x, y)

    def _jacobian(self, input, num_out):
        if isinstance(input, list):
            return [self._jacobian(elem, num_out) for elem in input]
        else:
            return torch.zeros(input.nElement(), num_out)

    def _tensors_in(self, x):
        if torch.isTensor(x):
            yield x
        else:
            for e in x:
                yield from self._tensors_in(e)

    def _clone_input(self, input):
        if isinstance(input, list):
            return [self._clone_input(i) for i in input]
        else:
            return input.clone()

    def _analytical_jacobian(self, module, input, jacobian_input=True, jacobian_parameters=True):
        module.forward(input)
        d_out = module.output.new().resizeAs(module.output)
        flat_d_out = d_out.view(-1)

        if jacobian_input:
            jacobian_input = self._jacobian(input, d_out.nElement())
            flat_jacobian_input = list(self._tensors_in(jacobian_input))
            flat_input = list(self._tensors_in(input))

        if jacobian_parameters:
            param, d_param = module.flattenParameters()
            jacobian_param = torch.zeros(param.nElement(), d_out.nElement())

        for i in range(flat_d_out.nElement()):
            d_out.zero()
            flat_d_out[i] = 1

            if jacobian_parameters:
                module.zeroGradParameters()

            d_input = module.updateGradInput(input, d_out)
            module.accGradParameters(input, d_out)

            if jacobian_input:
                for jacobian_x, d_x in zip(flat_jacobian_input, self._tensors_in(d_input)):
                    jacobian_x[:,i] = d_x
            if jacobian_parameters:
                jacobian_param[:,i] = d_param

        res = tuple()
        if jacobian_input:
            res += jacobian_input,
        if jacobian_parameters:
            res += jacobian_param,

        return res

    def _numerical_jacobian(self, module, input, jacobian_input=True, jacobian_parameters=True):
        perturbation = 1e-6
        module.forward(input)
        output_size = module.output.nElement()

        if jacobian_parameters:
            param, d_param = module.flattenParameters()

        def get_jacobian_wrt(input, x):
            jacobian = self._jacobian(x, output_size)

            # It's much easier to iterate over flattened lists of tensors.
            # These are reference to the same objects in jacobian, so any changes
            # will be reflected in it as well.
            x_tensors = [t for t in self._tensors_in(x)]
            j_tensors = [t for t in self._tensors_in(jacobian)]

            outa = torch.Tensor(output_size)
            outb = torch.Tensor(output_size)

            # TODO: compare structure
            for x_tensor, d_tensor in zip(x_tensors, j_tensors):
                flat_tensor = x_tensor.view(-1)
                for i in range(flat_tensor.nElement()):
                    orig = flat_tensor[i]
                    flat_tensor[i] = orig - perturbation
                    outa.copy(module.forward(input))
                    flat_tensor[i] = orig + perturbation
                    outb.copy(module.forward(input))
                    flat_tensor[i] = orig

                    outb.add(-1,outa).div(2*perturbation)
                    d_tensor[i] = outb

            return jacobian

        # To be able to use .view(-1) the Tensors must be contiguous
        def contiguous(input):
            if isinstance(input, list):
                return [contiguous(e) for e in input]
            else:
                return input.contiguous()
        input = contiguous(input)

        res = tuple()
        if jacobian_input:
            res += get_jacobian_wrt(input, input),
        if jacobian_parameters:
            res += get_jacobian_wrt(input, param),
        return res

    def check_jacobian(self, module, input, jacobian_input=True):
        jacobian_parameters = bool(module.parameters())
        analytical = self._analytical_jacobian(module, input, jacobian_input, jacobian_parameters)
        numerical = self._numerical_jacobian(module, input, jacobian_input, jacobian_parameters)
        analytical_t = self._tensors_in(analytical)
        numerical_t = self._tensors_in(numerical)
        # TODO: compare structure
        self.assertLessEqual(
            max(a.add(-1, n).abs().max() for a, n in zip(analytical_t, numerical_t)),
            PRECISION
        )

    def check_criterion_jacobian(self, criterion, input, target):
        eps = 1e-6
        criterion.forward(input, target)
        d_x = criterion.backward(input, target)
        numerical_d_x = self._clone_input(input)

        input_t = self._tensors_in(input)
        numerical_t = self._tensors_in(input)
        for x, d_x in zip(input_t, numerical_t):
            x = x.view(-1)
            d_x = d_x.view(-1)
            for i in range(x.nElement()):
                original = x[i]
                x[i] = original + eps
                fx1 = criterion.forward(input, target)
                x[i] = original - eps
                fx2 = criterion.forward(input, target)
                deriv = (fx1 - fx2) / (2*eps)
                d_x[i] = deriv
                x[i] = original

        # TODO: check structure
        input_t = self._tensors_in(input)
        numerical_t = self._tensors_in(input)
        self.assertLessEqual(
            max(a.add(-1, n).abs().max() for a, n in zip(input_t, numerical_t)),
            PRECISION
        )

    def test_Dropout(self):
        p = 0.2
        input = torch.Tensor(1000).fill(1-p)

        module = nn.Dropout(p)
        output = module.forward(input)
        self.assertLess(abs(output.mean() - (1-p)), 0.05)
        gradInput = module.backward(input, input)
        self.assertLess(abs(gradInput.mean() - (1-p)), 0.05)

        module = nn.Dropout(p, True)
        output = module.forward(input.clone())
        self.assertLess(abs(output.mean() - (1-p)), 0.05)
        gradInput = module.backward(input.clone(), input.clone())
        self.assertLess(abs(gradInput.mean() - (1-p)), 0.05)

    @unittest.skip("Not implemented")
    def test_SpatialDropout(self):
        p = 0.2
        b = random.randint(1, 5)
        w = random.randint(1, 5)
        h = random.randint(1, 5)
        nfeats = 1000
        input = torch.Tensor(b, nfeats, w, h).fill(1)
        module = nn.SpatialDropout(p)
        module.training()
        output = module.forward(input)
        self.assertLess(abs(output.mean() - (1-p)), 0.05)
        gradInput = module.backward(input, input)
        self.assertLess(abs(gradInput.mean() - (1-p)), 0.05)

    @unittest.skip("Not implemented")
    def test_VolumetricDropout(self):
        p = 0.2
        bsz = random.random(1,5)
        t = random.random(1,5)
        w = random.random(1,5)
        h = random.random(1,5)
        nfeats = 1000
        input = torch.Tensor(bsz, nfeats, t, w, h).fill(1)
        module = nn.VolumetricDropout(p)
        module.training()
        output = module.forward(input)
        self.assertLess(abs(output.mean() - (1-p)), 0.05)
        gradInput = module.backward(input, input)
        self.assertLess(abs(gradInput.mean() - (1-p)), 0.05)

    @unittest.skip("Not implemented")
    def test_ReLU(self):
        input = torch.randn(10, 20)
        module = nn.ReLU()
        output = module.forward(input)
        self.assertTrue(output[input >= 0].eq(input[input >= 0]).all())
        self.assertTrue(output[input < 0].eq(0).all())

    @unittest.skip("Not implemented")
    def test_ReLU6(self):
        input = torch.randn(10, 20).mul(10)
        module = nn.ReLU()
        output = module.forward(input)
        # TODO: check elements between 0 and 6
        self.assertTrue(output[input > 6].eq(6).all())
        self.assertTrue(output[input < 0].eq(0).all())

    def test_Copy(self):
        input = torch.randn(3,4).double()
        c = nn.Copy(torch.DoubleTensor, torch.FloatTensor)
        output = c.forward(input)
        self.assertEqual(torch.typename(output), 'torch.FloatTensor')
        self.assertEqual(output, input.float(), 1e-6)
        gradInput = c.backward(input, output.fill(1))
        self.assertEqual(torch.typename(gradInput), 'torch.DoubleTensor')
        self.assertEqual(gradInput, output.double(), 1e-6)
        c.dontCast = True
        c.double()
        self.assertEqual(torch.typename(output), 'torch.FloatTensor')

    def test_FlattenTable(self):
        input = [
            torch.rand(1),
            [
                torch.rand(2),
                [
                    torch.rand(3)
                ],
            ],
            torch.rand(4)
        ]
        gradOutput = [
            torch.rand(1),
            torch.rand(2),
            torch.rand(3),
            torch.rand(4)
        ]

        m = nn.FlattenTable()
        output = m.forward(input)
        self.assertEqual(len(output), 4)
        self.assertEqual(output[0], input[0])
        self.assertEqual(output[1], input[1][0])
        self.assertEqual(output[2], input[1][1][0])
        self.assertEqual(output[3], input[2])

        gradInput = m.backward(input, gradOutput)
        self.assertEqual(gradOutput[0], gradInput[0])
        self.assertEqual(gradOutput[1], gradInput[1][0])
        self.assertEqual(gradOutput[2], gradInput[1][1][0])
        self.assertEqual(gradOutput[3], gradInput[2])

        # More uglyness: FlattenTable doesn't rebuild the table every updateOutput
        # call, so we need to make sure that modifications to the input are
        # detected correctly (and that the table is correctly rebuilt.
        # CASE 1: Nothing changes so the output table shouldn't be redefined
        old_input_map = m.input_map
        old_output = m.output
        m.forward(input)
        self.assertEqual(old_input_map, m.input_map)
        self.assertEqual(old_output, m.output)

        # CASE 2: An element is added to the input table
        old_input_map = m.input_map
        old_output = m.output
        input[1].append(torch.rand(5))
        m.forward(input)
        self.assertNotEqual(old_input_map, m.input_map)
        self.assertNotEqual(old_output, m.output)

        # CASE 3: An element is removed from the input table
        old_input_map = m.input_map
        old_output = m.output
        input.pop()
        m.forward(input)
        self.assertNotEqual(old_input_map, m.input_map)
        self.assertNotEqual(old_output, m.output)

    def test_Concat(self):
        input = torch.randn(4, 2)
        num_modules = random.randint(2, 5)
        linears = [nn.Linear(2, 5) for i in range(num_modules)]

        m = nn.Concat(0)
        for l in linears:
            m.add(l)
            l.zeroGradParameters()
            l.weight.fill(1)
            l.bias.fill(0)

        output = m.forward(input)
        output2 = input.sum(1).expand(4, 5).repeatTensor(num_modules, 1)
        self.assertEqual(output2, output)

        gradInput = m.backward(input, torch.ones(output2.size()))
        gradInput2 = torch.ones(4, 2).fill(num_modules * 5)
        self.assertEqual(gradInput, gradInput2)

        gradWeight = input.sum(0).expand(5, 2)
        for l in linears:
            self.assertEqual(gradWeight, l.gradWeight)

    @unittest.skip('View not implemented')
    def test_Parallel(self):
        input = torch.randn(3, 4, 5)
        m = nn.Parallel(1, 3)
        m.add(nn.View(4, 5, 1))
        m.add(nn.View(4, 5, 1))
        m.add(nn.View(4, 5, 1))

        output = m.forward(input)
        output2 = input.transpose(0, 2).transpose(0, 1)
        self.assertEqual(output2, output)

        gradInput = m.backward(input, output2)
        self.assertEqual(gradInput, input)

    @unittest.skip('View not implemented')
    def test_ParallelTable(self):
        input = torch.randn(3, 4, 5)
        p = nn.ParallelTable()
        p.add(nn.View(4,5,1))
        p.add(nn.View(4,5,1))
        p.add(nn.View(4,5,1))
        m = nn.Sequential()
        m.add(nn.SplitTable(0))
        m.add(p)
        m.add(nn.JoinTable(2))

        output = m.forward(input)
        output2 = input.transpose(0,2).transpose(0,1)
        self.assertEqual(output2, output)

        gradInput = m.backward(input, output2)
        self.assertEqual(gradInput, input)

    def test_ConcatTable(self):
        input = [
                torch.randn(3, 4).float(), torch.randn(3, 4).float(), [torch.randn(3, 4).float()]
        ]
        _gradOutput = [
                torch.randn(3, 3,4).float(), torch.randn(3, 3,4).float(), torch.randn(3, 3,4).float()
        ]
        gradOutput = [
                [_gradOutput[0][0], _gradOutput[1][0], [_gradOutput[2][0]]],
                [_gradOutput[0][1], _gradOutput[1][1], [_gradOutput[2][1]]],
                [_gradOutput[0][2], _gradOutput[1][2], [_gradOutput[2][2]]]
        ]
        module = nn.ConcatTable()
        module.add(nn.Identity())
        module.add(nn.Identity())
        module.add(nn.Identity())
        module.float()

        output = module.forward(input)
        output2 = [input, input, input]
        self.assertEqual(output2, output)
        gradInput = module.backward(input, gradOutput)
        gradInput2 = [_gradOutput[0].sum(0).squeeze(0), _gradOutput[1].sum(0).squeeze(0), [_gradOutput[2].sum(0).squeeze(0)]]
        self.assertTrue(isinstance(gradInput, list))
        self.assertFalse(isinstance(gradInput[0], list))
        self.assertFalse(isinstance(gradInput[1], list))
        self.assertTrue(isinstance(gradInput[2], list))
        self.assertEqual(len(gradInput), 3)
        self.assertEqual(len(gradInput[2]), 1)
        for t1, t2 in zip(self._tensors_in(gradInput), self._tensors_in(gradInput2)):
            self.assertEqual(t1, t2)

        # test outputs for variable length inputs
        test = nn.ConcatTable()
        test.add(nn.Identity())
        test.add(nn.Identity())

        x = [torch.randn(5), torch.randn(5)]
        y = [torch.randn(5)]

        o1 = len(test.forward(x))
        go1 = len(test.backward(x, [x, x]))
        o2 = len(test.forward(y))
        go2 = len(test.backward(y, [y, y]))
        self.assertEqual(o1, 2)
        self.assertEqual(go1, 2)
        self.assertEqual(o2, 2)
        self.assertEqual(go2, 1)

    @unittest.skip('SpatialConvolutionMM not implemented')
    def test_DepthConcat(self):
        outputSize = torch.IntTensor((5, 6, 7, 8))
        input = torch.randn(2, 3, 12, 12)
        gradOutput = torch.randn(2, outputSize.sum(), 12, 12)
        concat = nn.DepthConcat(1)
        concat.add(nn.SpatialConvolutionMM(3, outputSize[0], 1, 1, 1, 1)) #> 2, 5, 12, 12
        concat.add(nn.SpatialConvolutionMM(3, outputSize[1], 3, 3, 1, 1)) #> 2, 6, 10, 10
        concat.add(nn.SpatialConvolutionMM(3, outputSize[2], 4, 4, 1, 1)) #> 2, 7, 9, 9
        concat.add(nn.SpatialConvolutionMM(3, outputSize[3], 5, 5, 1, 1)) #> 2, 8, 8, 8
        concat.zeroGradParameters()
        # forward/backward
        outputConcat = concat.forward(input)
        gradInputConcat = concat.backward(input, gradOutput)
        # the spatial dims are the largest, the nFilters is the sum
        output = torch.Tensor(2, outputSize.sum(), 12, 12).zero() # zero for padding
        narrows = ( (slice(), (1, 5), slice(), slice()), (slice(), (6, 11), (2, 11), (2, 11)), (slice(), (12, 18), (2, 10), (2, 10)), (slice(), (19, 26), (3, 10), (3, 10)) )
        gradInput = input.clone().zero()
        for i in range(1, 4+1):
           conv = concat.get(i)
           gradWeight = conv.gradWeight.clone()
           conv.zeroGradParameters()
           output[narrows[i]].copy(conv.forward(input))
           gradInput.add(conv.backward(input, gradOutput[narrows[i]]))
           self.assertEqual(gradWeight, conv.gradWeight)

        self.assertEqual(output, outputConcat)
        self.assertEqual(gradInput, gradInputConcat)

    def test_Contiguous(self):
        input = torch.randn(10, 10, 10)
        noncontig = input[:, 4]
        module = nn.Contiguous()
        assert not noncontig.isContiguous()
        output = module.forward(noncontig)
        self.assertEqual(output, noncontig)
        self.assertTrue(output.contiguous())

    def test_Index(self):
        net = nn.Index(0)

        # test 1D
        input = [torch.Tensor((10, 20, 30)), torch.LongTensor((0, 1, 1, 2))]
        output = net.forward(input)
        self.assertEqual(output, torch.Tensor((10, 20, 20, 30)))

        gradOutput = torch.Tensor((1, 1, 1, 3))
        gradInput = net.backward(input, gradOutput)
        self.assertEqual(gradInput[0], torch.Tensor((1, 2, 3)))

        # test 2D
        input = [torch.Tensor(((10, 20), (30, 40))), torch.LongTensor((0, 0))]
        output = net.forward(input)
        self.assertEqual(output, torch.Tensor(((10, 20), (10, 20))))

        gradOutput = torch.Tensor(((1, 2), (1, 2)))
        gradInput = net.backward(input, gradOutput)
        self.assertEqual(gradInput[0], torch.Tensor(((2, 4), (0, 0))))

    def test_L1Penalty(self):
        weight = 1
        m = nn.L1Penalty(weight, False, False)

        input = torch.rand(2,10).add(-0.5)
        input[0][0] = 0

        m.forward(input)
        grad = m.backward(input, torch.ones(input.size()))

        self.assertEqual(input.clone().abs().sum() * weight, m.loss)

        true_grad = (input.gt(0).typeAs(grad) +
            input.lt(0).typeAs(grad).mul(-1)).mul(weight)
        self.assertEqual(true_grad, grad)

    def test_MaskedSelect(self):
        input = torch.randn(4, 5)
        mask = torch.ByteTensor(4, 5).bernoulli()
        module = nn.MaskedSelect()
        out = module.forward([input, mask])
        self.assertEqual(input.maskedSelect(mask), out)

        gradOut = torch.Tensor((20, 80))
        input = torch.Tensor(((10, 20), (30, 40)))
        inTarget = torch.Tensor(((20, 0), (0, 80)))
        mask = torch.ByteTensor(((1, 0), (0, 1)))
        module = nn.MaskedSelect()
        module.forward([input, mask])
        gradIn = module.backward([input, mask], gradOut)
        self.assertEqual(inTarget, gradIn[0])

    def test_MultiCriterion(self):
        input = torch.rand(2, 10)
        target = torch.Tensor((1, 8))
        nll = nn.ClassNLLCriterion()
        nll2 = nn.CrossEntropyCriterion()
        mc = nn.MultiCriterion().add(nll, 0.5).add(nll2)

        output = mc.forward(input, target)
        output2 = nll.forward(input, target)/2 + nll2.forward(input, target)

        self.assertEqual(output, output2)
        gradInput = mc.backward(input, target)
        gradInput2 = nll.backward(input, target).clone().div(2).add(nll2.backward(input, target))
        self.assertEqual(gradInput, gradInput2)

        # test type
        mc.float()
        gradInput = gradInput.clone()
        input3 = input.float()
        target3 = target.float()
        output3 = mc.forward(input3, target3)
        gradInput3 = mc.backward(input3, target3)
        self.assertEqual(output, output3)
        self.assertEqual(gradInput.float(), gradInput3)

        # test table input
        # TODO: enable when ParallelCriterion is ready
        # mc.double()
        # input = [torch.randn(2, 10), [torch.randn(2, 10), torch.randn(2, 10)]]
        # target = [torch.IntTensor((1, 8)), [torch.IntTensor((5, 6)), torch.IntTensor((4, 3))]]
        # pnllc = nn.ParallelCriterion().add(nll).add(nn.ParallelCriterion().add(nll.clone()).add(nll.clone()))
        # pnllc2 = nn.ParallelCriterion().add(nll2).add(nn.ParallelCriterion().add(nll2.clone()).add(nll2.clone()))
        # mc = nn.MultiCriterion().add(pnllc, 0.5).add(pnllc2)
        # output = mc.forward(input, target)
        # output2 = pnllc.forward(input, target)/2 + pnllc2.forward(input, target)
        # self.assertEqual(output, output2)
        # gradInput = mc.backward(input, target)
        # gradInput2 = pnllc.clone().backward(input, target)
        # gradInput2b = pnllc2.backward(input, target)
        # gradInput2[0].div(2).add(gradInput2b[0])
        # gradInput2[1][0].div(2).add(gradInput2b[1][0])
        # gradInput2[1][1].div(2).add(gradInput2b[1][1])
        # self.assertEqual(gradInput[1], gradInput2[0])
        # self.assertEqual(gradInput[1][9], gradInput2[1][0])
        # self.assertEqual(gradInput[1][1], gradInput2[1][1])


if __name__ == '__main__':
    prepare_simple_tests()
    unittest.main()

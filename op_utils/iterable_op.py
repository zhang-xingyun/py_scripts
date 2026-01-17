import copy

from hatbc.easydict import EasyDict
from hatbc.utils import _as_list
from hatbc.workflow.engine import SymbolExecutor
from hatbc.workflow.operator import Operator
from hatbc.workflow.proxy import WorkflowVariable, get_traced_graph
from hatbc.workflow.symbol import Symbol

__all__ = [
    "IterableOp",
    "ExecuteGraphCallback",
]


class _IterableOutput(object):
    def __init__(self, callback, iterable_input_keys, inputs):
        self.callback = callback
        self.iterable_input_keys = iterable_input_keys
        self.inputs = inputs

    def __iter__(self):
        input_iterators = dict()
        inputs = dict()
        for name, value in self.inputs.items():
            if name in self.iterable_input_keys:
                input_iterators[name] = iter(value)
            else:
                inputs[name] = value
        while True:
            inputs = copy.copy(inputs)
            end = False
            for name, iterator in input_iterators.items():
                try:
                    data = next(iterator)
                    if end:
                        raise RuntimeError(
                            "Input length of {self.iterable_input_keys} are not equal"  # noqa
                        )
                except StopIteration:
                    end = True
                    continue
                inputs[name] = data
            if end:
                return
            ret = self.callback(inputs)
            yield ret


class IterableOp(Operator):
    def __init__(self, callback, iterable_input_keys):
        super(IterableOp, self).__init__()
        self.callback = callback
        self.iterable_input_keys = _as_list(iterable_input_keys)

    def forward(self, **inputs):

        iterable_output = _IterableOutput(
            self.callback, self.iterable_input_keys, inputs
        )
        return iterable_output


class ExecuteGraphCallback(object):
    def __init__(self, graph, output_keys=None):
        if isinstance(graph, WorkflowVariable):
            graph = get_traced_graph(graph)
        assert isinstance(graph, Symbol)
        self.num_outputs = len(graph)
        self.executor = SymbolExecutor(graph)
        if output_keys is not None:
            output_keys = _as_list(output_keys)
            assert (
                len(output_keys) == self.num_outputs
            ), f"{len(output_keys)} VS. {self.num_outputs}"
        self.output_keys = output_keys

    def __call__(self, inputs):
        outputs = self.executor(inputs)
        if self.output_keys is not None:
            if self.num_outputs == 1:
                outputs = [
                    outputs,
                ]
            outputs = dict(
                (
                    (key_i, out_i)
                    for key_i, out_i in zip(self.output_keys, outputs)
                )
            )
            outputs = EasyDict(outputs)
        return outputs

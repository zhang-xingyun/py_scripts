import inspect
from functools import partial
from typing import Callable, Iterable, Union

from hatbc.distributed.client._process_pool_executor import ProcessPoolExecutor
from hatbc.distributed.multi_worker_iter import MultiWorkerIter
from hatbc.workflow.engine.simple_parallel import SimpleParallelExecutor
from hatbc.workflow.operator import Operator
from hatbc.workflow.proxy import WorkflowVariable, get_traced_graph
from hatbc.workflow.symbol import Symbol
from tqdm import tqdm

__all__ = [
    "SimpleParallelExecuteGraphFunc",
    "CustomFunc",
    "multipprocessing_wrap",
]


class CustomFunc(Operator):
    def __init__(self, func):
        super(CustomFunc, self).__init__()
        self.func = func

    def forward(self, *args, **kwargs):
        return self.func(*args, **kwargs)


class SimpleParallelExecuteGraphFunc(object):
    def __init__(self, graph, **kwargs):
        if isinstance(graph, WorkflowVariable):
            graph = get_traced_graph(graph)
        assert isinstance(
            graph, Symbol
        ), f"Expected Symbol, but get {str(type(graph))}"  # noqa
        self.graph = graph
        self.num_outputs = len(graph)
        self.kwargs = kwargs
        self.key2executor = dict()

    def __getstate__(self):
        state = self.__dict__.copy()
        state["key2executor"] = dict()
        return state

    def __call__(self, num_worker=0, backend=None, **inputs):
        key = (num_worker, backend)
        if key not in self.key2executor:
            self.key2executor[key] = SimpleParallelExecutor(
                self.graph,
                num_worker=num_worker,
                backend=backend,
                **self.kwargs,
            )
        executor = self.key2executor[key]

        output = executor(inputs)
        return output


def multipprocessing_wrap(
    input_iter: Iterable,
    input_kwargs: dict,
    work_fn: Union[Operator, Callable],
    num_workers: int = 0,
    keep_order: bool = True,
):
    """Seletor multiple processing wrapper.

    Args:
        input_iter (Iterable): input iter.
        input_kwargs (dict): input_kwargs for work_fn.
        work_fn (Operator): work function whose first argument is
            element of input_iter.
        num_workers (int, optional): workers number. Defaults to 0.

    Returns:
        List: result list.
    """
    if inspect.isclass(work_fn):
        differ = work_fn(**input_kwargs)
        assert isinstance(work_fn, Callable)
    elif isinstance(work_fn, Callable):
        differ = partial(work_fn, **input_kwargs)
    if num_workers > 0:
        ret = []
        worker_pool = ProcessPoolExecutor(
            max_workers=num_workers,
        )
        worker_iter = MultiWorkerIter(
            input_iter=input_iter,
            worker_fn=differ,
            client=worker_pool,
            keep_order=keep_order,
        )
        for input_iter_i in tqdm(worker_iter):
            ret.append(input_iter_i)

        worker_pool.shutdown()
    else:
        ret = [differ(input_iter_i) for input_iter_i in input_iter]
    ret = [r for r in ret if r is not None]
    return ret

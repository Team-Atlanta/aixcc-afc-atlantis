import queue
import threading
import os
import traceback
import json
import shutil

from loguru import logger

from corpus import Corpus
from .resources import corpus_queue
from tracer import DynamoRIOTracer
from tracer.model import Relations


def worker_tracer(stop_event: threading.Event):
    while not stop_event.is_set():
        try:
            corpus: Corpus = corpus_queue.get(timeout=0.5)
            process_corpus(corpus)
            corpus_queue.task_done()

        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"Error in worker_tracer: {traceback.format_exc()}")


def process_corpus(corpus: Corpus) -> None:
    target_dir = os.getenv("OUT")

    logger.info(f"Tracing: {corpus.harness} - {os.path.basename(corpus.path)}")
    tracer = DynamoRIOTracer(target_dir)
    tracer.trace(corpus.harness, corpus.data)

    traced_edges = tracer.parse_raw_trace_data_for_edges()
    traced_all = tracer.parse_raw_data_for_trace()

    logger.info(f"Dump trace info: {corpus.harness} - {os.path.basename(corpus.path)}")
    dump_trace_output(corpus, traced_edges, "edges")
    dump_trace_output(corpus, traced_all, "trace")
    tracer.cleanup()


def dump_trace_output(
    corpus: Corpus, traced_funcs: Relations | dict[int, Relations], suffix: str
) -> None:
    trace_outputdir = os.path.abspath(os.getenv("CRS_SARIF_TRACER_TRACE_OUTPUTDIR"))

    harness_dir = os.path.join(trace_outputdir, corpus.harness)
    if not os.path.isdir(harness_dir):
        os.makedirs(harness_dir, exist_ok=True)

    trace_output_path = os.path.join(
        harness_dir, f"{os.path.basename(corpus.path)}.{suffix}"
    )

    tmp_trace_output_path = trace_output_path + ".tracing"
    if isinstance(traced_funcs, dict):
        dumped_model = dict()
        for thread_id, relations in traced_funcs.items():
            dumped_model[thread_id] = [relation.model_dump() for relation in relations]

        with open(tmp_trace_output_path, "w") as f:
            f.write(json.dumps(dumped_model))
        shutil.move(tmp_trace_output_path, trace_output_path)

    else:
        with open(tmp_trace_output_path, "w") as f:
            f.write(json.dumps([relation.model_dump() for relation in traced_funcs]))
        shutil.move(tmp_trace_output_path, trace_output_path)

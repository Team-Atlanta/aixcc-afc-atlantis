import glob
import os
import hashlib

from .model import Corpus

searched_corpus = list()


class CorpusSearcher:
    def __init__(self, corpus_directory: str):
        # Assume shared directory structure:
        # root - cp - harness_name - corpuses
        # Start with cp scope
        self.corpus_directory = corpus_directory

    def search_new_corpus(self) -> list[Corpus]:
        base_fuzzer_directories = ["crs-multilang", "crs-userspace"]
        corpuses = list()
        for base_fuzzer_directory in base_fuzzer_directories:
            corpus_directory_path = os.path.join(
                self.corpus_directory, base_fuzzer_directory
            )
            if os.path.isdir(corpus_directory_path):
                glob_result = glob.glob(
                    f"{corpus_directory_path}{os.sep}**", recursive=True
                )
                corpuses.extend(
                    [corpus_f for corpus_f in glob_result if os.path.isfile(corpus_f)]
                )

        new_corpuses = list()
        for corpus_path in corpuses:
            if corpus_path not in searched_corpus:
                harness_name = os.path.basename(os.path.dirname(corpus_path))
                with open(corpus_path, "rb") as f:
                    corpus_data = f.read()

                hasher = hashlib.sha256()
                hasher.update(corpus_data + harness_name.encode())

                corpus_id = hasher.hexdigest()
                new_corpus = Corpus(
                    harness=harness_name,
                    data=corpus_data,
                    path=corpus_path,
                    corpus_id=corpus_id,
                )

                searched_corpus.append(corpus_path)
                new_corpuses.append(new_corpus)

        return new_corpuses

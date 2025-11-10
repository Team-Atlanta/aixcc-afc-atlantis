FROM ghcr.io/aixcc-finals/base-runner:v1.3.0 AS multilang-base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && \
    apt upgrade -y && \
    apt install -y build-essential libz3-dev zlib1g-dev ninja-build ca-certificates gpg wget nlohmann-json3-dev lsb-release software-properties-common ripgrep

# Install Cargo
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y --default-toolchain 1.87
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Python 3.10 # deadsnakes ended support for ubuntu20.04
ARG PY_VER=3.10.14
WORKDIR /usr/src
RUN curl -fsSLO https://www.python.org/ftp/python/${PY_VER}/Python-${PY_VER}.tgz \
    && tar -xzf Python-${PY_VER}.tgz
WORKDIR /usr/src/Python-${PY_VER}
RUN ./configure --enable-optimizations --with-ensurepip=install \
    && make -j"$(nproc)" \
    && make altinstall

RUN apt update && \
    apt install -y protobuf-compiler ripgrep

WORKDIR /
RUN python3.10 -m venv crs_env && . crs_env/bin/activate
ENV PATH="/crs_env/bin:$PATH"
RUN pip3 install --upgrade pip

# Install LLVM/Clang
RUN wget https://apt.llvm.org/llvm.sh && \
    chmod +x llvm.sh && \
    ./llvm.sh 14 && \
    rm llvm.sh

RUN update-alternatives --install /usr/bin/clang clang /usr/bin/clang-14 100 && \
    update-alternatives --install /usr/bin/clangd clangd /usr/bin/clangd-14 100 && \
    update-alternatives --install /usr/bin/clang++ clang++ /usr/bin/clang++-14 100 && \
    update-alternatives --install /usr/bin/clang-cpp clang-cpp /usr/bin/clang-cpp-14 100

# Install cmake
RUN (test -f /usr/share/doc/kitware-archive-keyring/copyright || \
        wget -O - https://apt.kitware.com/keys/kitware-archive-latest.asc 2>/dev/null | gpg --dearmor - | tee /usr/share/keyrings/kitware-archive-keyring.gpg >/dev/null) && \
    echo 'deb [signed-by=/usr/share/keyrings/kitware-archive-keyring.gpg] https://apt.kitware.com/ubuntu/ focal main' | tee /etc/apt/sources.list.d/kitware.list >/dev/null && \
    apt update && \
    (test -f /usr/share/doc/kitware-archive-keyring/copyright || \
        rm /usr/share/keyrings/kitware-archive-keyring.gpg) && \
    apt install -y kitware-archive-keyring cmake

################################################################################
# Build UniAFL
################################################################################

FROM multilang-base AS uniafl
WORKDIR /home/crs/uniafl
COPY ./uniafl /home/crs/uniafl
COPY ./fuzzdb/*.toml /home/crs/fuzzdb/
COPY ./fuzzdb/src /home/crs/fuzzdb/src
COPY ./libs/libFDP /home/crs/libs/libFDP
COPY ./libs/z3.rs /home/crs/libs/z3.rs
COPY ./customgen /home/crs/customgen
COPY ./testlang /home/crs/testlang
ENV CXXSTDLIB_ORIG=${CXXSTDLIB}
ENV CXXSTDLIB=stdc++
RUN cargo build --release
RUN cargo build --tests --release
ENV CXXSTDLIB=${CXXSTDLIB_ORIG}

################################################################################
# Build llvm-cov-custom
################################################################################

FROM multilang-base AS llvm-cov-custom
RUN git clone --depth 1 --branch llvmorg-18.1.8 https://github.com/llvm/llvm-project.git /llvm-project && \
    cd /llvm-project && \
    git switch -c llvm-cov-custom
RUN rm -rf /llvm-project/build
RUN rm -rf /llvm-project/install
COPY bin/symbolizer/patch.diff /llvm-project/patch.diff
WORKDIR /llvm-project
RUN git apply patch.diff
WORKDIR /llvm-project/build
RUN cmake -G Ninja ../llvm \
  -DCMAKE_BUILD_TYPE=Release \
  -DLLVM_ENABLE_PROJECTS="clang;compiler-rt" \
  -DLLVM_TARGETS_TO_BUILD="X86" \
  -DCMAKE_INSTALL_PREFIX=../install \
  -DCMAKE_C_COMPILER=clang \
  -DCMAKE_CXX_COMPILER=clang++
RUN ninja llvm-cov
RUN ninja install llvm-cov

################################################################################
# Build jazzer for function-tracer
################################################################################

FROM multilang-base AS tracer-jazzer-builder

RUN apt-get update && apt-get install -y apt-transport-https curl gnupg && \
curl -fsSL https://bazel.build/bazel-release.pub.gpg | gpg --dearmor > /usr/share/keyrings/bazel-archive-keyring.gpg && \
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/bazel-archive-keyring.gpg] https://storage.googleapis.com/bazel-apt stable jdk1.8" | tee /etc/apt/sources.list.d/bazel.list

RUN apt-get update && apt-get install -y maven bazel-7.3.0

RUN ln -s /usr/bin/bazel-7.3.0 /usr/bin/bazel

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV JAVA_15_HOME=/usr/lib/jvm/java-15-openjdk-amd64
ENV JVM_LD_LIBRARY_PATH=$JAVA_HOME/lib/server
ENV PATH=$PATH:$JAVA_HOME/bin

ENV CRS_SARIF_TRACER_JAZZER_SRC=/jazzer

RUN useradd -m jazzer_user
COPY ./function-tracer/tracer-java/jazzer $CRS_SARIF_TRACER_JAZZER_SRC

RUN chown -R jazzer_user:jazzer_user $CRS_SARIF_TRACER_JAZZER_SRC

USER jazzer_user

WORKDIR $CRS_SARIF_TRACER_JAZZER_SRC

RUN echo "build --java_runtime_version=local_jdk_17" >> .bazelrc && \
    echo "build --cxxopt=-stdlib=libc++" >> .bazelrc && \
    echo "build --linkopt=-lc++" >> .bazelrc

RUN bazel build \
    //src/main/java/com/code_intelligence/jazzer:jazzer_standalone_deploy.jar \
    //deploy:jazzer-api \
    //deploy:jazzer-junit \
    //launcher:jazzer


USER root
RUN mkdir /jazzer_output
RUN chmod 777 /jazzer_output
USER jazzer_user

RUN cp $(bazel cquery --output=files //src/main/java/com/code_intelligence/jazzer:jazzer_standalone_deploy.jar) /jazzer_output/jazzer_standalone_deploy.jar
RUN cp $(bazel cquery --output=files //launcher:jazzer) /jazzer_output/jazzer_driver
RUN cp $(bazel cquery --output=files //deploy:jazzer-api) /jazzer_output/jazzer_api_deploy.jar
RUN cp $(bazel cquery --output=files //deploy:jazzer-junit) /jazzer_output/jazzer_junit.jar

################################################################################
# Build dynamorio for function-tracer
################################################################################

FROM multilang-base AS tracer-dynamorio-builder

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    wget \
    tar \
    python3 \
    python3-pip

RUN python3 -m pip install loguru pydantic

COPY ./function-tracer/tracer-c/tools /trace_tools

RUN cd /trace_tools/dynamorio && \
    chmod +x build.sh && \
    ./build.sh


################################################################################
# CRS Main
################################################################################

FROM multilang-base
RUN apt update && apt install -y curl git build-essential libssl-dev zlib1g-dev \
    sqlite3 libsqlite3-dev xxd \
    && curl https://pyenv.run | bash
ENV PATH="/root/.pyenv/bin:/root/.pyenv/shims:$PATH"
RUN pyenv install 3.11.8 && pyenv global 3.11.8

RUN pip3 install maturin
RUN apt install redis-server -y
RUN apt install pigz -y
RUN apt install graphviz -y
RUN apt install unifdef -y

# Copy from multilang-builder for CP build
COPY --from=llvm-cov-custom /llvm-project/install/bin/llvm-cov /usr/local/bin/symbolizer/llvm-cov-custom
COPY --from=multilang-builder /symcc /symcc
COPY scripts/lsp-prepare.sh /multilang-builder/scripts/lsp-prepare.sh

# Build FuzzDB
WORKDIR /home/crs
RUN git clone https://chromium.googlesource.com/chromium/src/tools/code_coverage
WORKDIR /home/crs/code_coverage
RUN git checkout 22e1f766319790ac6399eb23341a5d6848e77603
COPY ./fuzzdb /home/crs/fuzzdb
WORKDIR /home/crs/fuzzdb
RUN ./build.sh

# Build libFDP
COPY ./libs/libFDP /home/crs/libs/libFDP
WORKDIR /home/crs/libs/libFDP
RUN ./build_pymodule.sh

# Build CustomGen
COPY ./customgen /home/crs/customgen
WORKDIR /home/crs/customgen
RUN ./build.sh

# Build Testlang
COPY ./testlang /home/crs/testlang
WORKDIR /home/crs/testlang
RUN ./build.sh

## Build harness-reverser
COPY ./reverser/harness-reverser /home/crs/reverser/harness-reverser
WORKDIR /home/crs/reverser/harness-reverser
RUN pip3 install -r ./requirements.txt
WORKDIR /home/crs/reverser/harness-reverser/static
RUN ./build.sh

# Build libCRS
COPY ./libs/libCRS /home/crs/libs/libCRS
RUN pip3 install /home/crs/libs/libCRS

# Build dictgen
COPY ./dictgen/requirements.txt /home/crs/dictgen/requirements.txt
RUN pip3 install -r /home/crs/dictgen/requirements.txt

# Build multilspy
COPY ./libs/multilspy /home/crs/libs/multilspy
RUN pip3 install /home/crs/libs/multilspy

# Build joern
COPY ./joern /home/crs/libs/joern
WORKDIR /home/crs/libs/joern
RUN python3 -m build
RUN pip3 install /home/crs/libs/joern/dist/*.whl

# Setup function-tracer (jazzer)
# ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
# ENV JAVA_15_HOME=/usr/lib/jvm/java-15-openjdk-amd64
# ENV JVM_LD_LIBRARY_PATH=$JAVA_HOME/lib/server
# ENV PATH=$PATH:$JAVA_HOME/bin

ENV TRACER_PATH=/tracer
ENV TRACER_JAVA_PATH=/tracer/java
ENV TRACER_WORKDIR=/tracer_workdir

ENV TRACER_ENGINES=/tracer_engines

RUN mkdir $TRACER_ENGINES

ENV TRACER_JAZZER_API_PATH="$TRACER_ENGINES/jazzer_api_deploy.jar"
ENV TRACER_JAZZER_JUNIT_PATH="$TRACER_ENGINES/jazzer_junit.jar"
ENV TRACER_JAZZER_DRIVER_PATH="$TRACER_ENGINES/jazzer_driver"
ENV TRACER_JAZZER_AGENT_PATH="$TRACER_ENGINES/jazzer_agent_deploy.jar"

COPY --from=tracer-jazzer-builder /jazzer_output/jazzer_standalone_deploy.jar $TRACER_JAZZER_AGENT_PATH
COPY --from=tracer-jazzer-builder /jazzer_output/jazzer_driver $TRACER_JAZZER_DRIVER_PATH
COPY --from=tracer-jazzer-builder /jazzer_output/jazzer_api_deploy.jar $TRACER_JAZZER_API_PATH
COPY --from=tracer-jazzer-builder /jazzer_output/jazzer_junit.jar $TRACER_JAZZER_JUNIT_PATH

COPY ./function-tracer/tracer-java/src $TRACER_JAVA_PATH

# Setup function-tracer (dynamorio)
ENV TRACER_C_PATH=/tracer/c
ENV TRACE_TOOL_DIR=/trace_tools

ENV TRACER_DYNAMORIO_TOOL_DIR=$TRACE_TOOL_DIR/dynamorio
ENV DYNAMORIO_HOME=$TRACER_DYNAMORIO_TOOL_DIR/DynamoRIO-Linux-11.90.20147
ENV DYNAMORIO_PLUGIN=$TRACER_DYNAMORIO_TOOL_DIR/libfunction_trace.so

COPY --from=tracer-dynamorio-builder $DYNAMORIO_HOME/bin64 $DYNAMORIO_HOME/bin64
COPY --from=tracer-dynamorio-builder $DYNAMORIO_HOME/lib64 $DYNAMORIO_HOME/lib64
COPY --from=tracer-dynamorio-builder $DYNAMORIO_HOME/lib32 $DYNAMORIO_HOME/lib32

RUN mkdir $DYNAMORIO_HOME/ext
COPY --from=tracer-dynamorio-builder $DYNAMORIO_HOME/ext/lib64 $DYNAMORIO_HOME/ext/lib64

COPY --from=tracer-dynamorio-builder $DYNAMORIO_PLUGIN $DYNAMORIO_PLUGIN

COPY ./function-tracer/tracer-c/src $TRACER_C_PATH

# Build mlla
COPY ./blob-gen/multilang-llm-agent /home/crs/blob-gen/multilang-llm-agent
WORKDIR /home/crs/blob-gen/multilang-llm-agent
RUN pip3 install -r ./requirements_docker.txt

COPY requirements.txt /home/crs/requirements.txt
RUN pip3 install -r /home/crs/requirements.txt

# Copy Uniafl
COPY --from=uniafl /home/crs/uniafl /home/crs/uniafl
COPY --from=uniafl /root/.cargo /root/.cargo
COPY --from=uniafl /home/crs/libs/z3.rs /home/crs/libs/z3.rs
COPY ./constraint-gen /home/crs/constraint-gen
WORKDIR /home/crs/constraint-gen
RUN python3.10 -m venv ./env
RUN bash -c 'source ./env/bin/activate && pip install .'

COPY ./dictgen /home/crs/dictgen/
COPY bin/* /usr/local/bin/
COPY static /home/crs/static
WORKDIR /home/crs/

ENV PATH="/usr/local/bin/symbolizer:$PATH"

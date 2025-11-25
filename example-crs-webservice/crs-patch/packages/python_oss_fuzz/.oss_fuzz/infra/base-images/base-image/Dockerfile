# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
################################################################################

# Base image for all other images.

ARG parent_image=ubuntu:20.04@sha256:4a45212e9518f35983a976eead0de5eecc555a2f047134e9dd2cfc589076a00d

FROM $parent_image

ENV DEBIAN_FRONTEND noninteractive
# Install tzadata to match ClusterFuzz
# (https://github.com/google/oss-fuzz/issues/9280).

# Use Azure mirrors for consistent apt repository access.
RUN cp /etc/apt/sources.list /etc/apt/sources.list.backup && \
    sed -i 's|http://archive.ubuntu.com/ubuntu/|http://azure.archive.ubuntu.com/ubuntu/|g' /etc/apt/sources.list && \
    sed -i 's|http://security.ubuntu.com/ubuntu/|http://azure.archive.ubuntu.com/ubuntu/|g' /etc/apt/sources.list


RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y libc6-dev binutils libgcc-9-dev tzdata locales locales-all && \
    apt-get autoremove -y

ENV OUT=/out
ENV SRC=/src
ENV WORK=/work
ENV PATH="$PATH:/out"
ENV HWASAN_OPTIONS=random_tags=0
#set locale to utf8
ENV LC_ALL=C.UTF-8

RUN mkdir -p $OUT $SRC $WORK && chmod a+rwx $OUT $SRC $WORK

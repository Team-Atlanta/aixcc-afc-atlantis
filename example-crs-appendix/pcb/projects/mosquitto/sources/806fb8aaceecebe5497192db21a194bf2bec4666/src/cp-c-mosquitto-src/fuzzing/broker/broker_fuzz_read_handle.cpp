/*
Copyright (c) 2023 Cedalo GmbH

All rights reserved. This program and the accompanying materials
are made available under the terms of the Eclipse Public License 2.0
and Eclipse Distribution License v1.0 which accompany this distribution.

The Eclipse Public License is available at
   https://www.eclipse.org/legal/epl-2.0/
and the Eclipse Distribution License is available at
  http://www.eclipse.org/org/documents/edl-v10.php.

SPDX-License-Identifier: EPL-2.0 OR BSD-3-Clause

Contributors:
   Roger Light - initial implementation and documentation.
*/

#include "fuzz_packet_read_base.h"

extern "C" int fuzz_packet_read_init(struct mosquitto *context)
{
	return 0;
}

extern "C" void fuzz_packet_read_cleanup(struct mosquitto *context)
{
}

extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
	return fuzz_packet_read_base(data, size, handle__packet);
}

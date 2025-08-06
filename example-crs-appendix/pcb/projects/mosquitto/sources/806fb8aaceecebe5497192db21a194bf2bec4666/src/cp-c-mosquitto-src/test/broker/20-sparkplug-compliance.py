#!/usr/bin/env python3

from mosq_test_helper import *
import uuid

def tck_id_conformance_mqtt_qos0(port, proto_ver):
    # A Sparkplug conformant MQTT Server MUST support publish and subscribe on
    # QoS 0

    topic = str(uuid.uuid4())
    payload = str(uuid.uuid4())
    client = mosq_test.sub_helper(port, topic, qos=0, proto_ver=proto_ver)
    publish_packet = mosq_test.gen_publish(topic, qos=0, payload=payload, retain=False, proto_ver=proto_ver)
    mosq_test.do_send_receive(client, publish_packet, publish_packet, error_string="tck-id-conformance-mqtt-qos0")
    client.close()


def tck_id_conformance_mqtt_qos1(port, proto_ver):
    # A Sparkplug conformant MQTT Server MUST support publish and subscribe on
    # QoS 1

    topic = str(uuid.uuid4())
    payload = str(uuid.uuid4())
    client = mosq_test.sub_helper(port, topic, qos=1, proto_ver=proto_ver)

    publish_packet = mosq_test.gen_publish(topic, qos=1, mid=1, payload=payload, retain=False, proto_ver=proto_ver)
    puback_packet = mosq_test.gen_puback(mid=1, proto_ver=proto_ver)

    client.send(publish_packet)
    mosq_test.receive_unordered(client, publish_packet, puback_packet, "tck-id-conformance-mqtt-qos1")
    client.close()


def tck_id_conformance_mqtt_will_messages(port, proto_ver):
    # A Sparkplug conformant MQTT Server MUST support all aspects of Will
    # Messages including use of the retain flag and QoS 1
    pass


def tck_id_conformance_mqtt_retained(port, proto_ver):
    # A Sparkplug conformant MQTT Server MUST support all aspects of the retain
    # flag

    topic = str(uuid.uuid4())
    payload = str(uuid.uuid4())
    client = mosq_test.pub_helper(port, proto_ver=proto_ver)

    publish_packet = mosq_test.gen_publish(topic, qos=0, payload=payload, retain=True, proto_ver=proto_ver)
    subscribe_packet = mosq_test.gen_subscribe(mid=1, topic=topic, qos=0, proto_ver=proto_ver)
    suback_packet = mosq_test.gen_suback(mid=1, qos=0, proto_ver=proto_ver)

    client.send(publish_packet)
    client.send(subscribe_packet)
    mosq_test.receive_unordered(client, publish_packet, suback_packet, "tck-id-conformance-mqtt-retained")
    client.close()


def do_tests():
    rc = 1
    port = mosq_test.get_port()
    broker = mosq_test.start_broker(filename=os.path.basename(__file__), port=port)

    try:
        tck_id_conformance_mqtt_qos0(port, 4)
        tck_id_conformance_mqtt_qos0(port, 5)

        tck_id_conformance_mqtt_qos1(port, 4)
        tck_id_conformance_mqtt_qos1(port, 5)

        tck_id_conformance_mqtt_will_messages(port, 4)
        tck_id_conformance_mqtt_will_messages(port, 5)

        tck_id_conformance_mqtt_retained(port, 4)
        tck_id_conformance_mqtt_retained(port, 5)

        rc = 0
    except Exception as e:
        print(e)
    finally:
        broker.terminate()
        if mosq_test.wait_for_subprocess(broker):
            print("broker not terminated")
            if rc == 0: rc=1
        (stdo, stde) = broker.communicate()
        if rc:
            print(stde.decode('utf-8'))
            exit(rc)

if __name__ == '__main__':
    do_tests()

from unittest.mock import Mock, patch

from coletor import ColetorOPC


@patch('influxdb.InfluxDBClient')
def test_registrar_heartbeat_uses_dedicated_measurement(client_class):
    client = Mock()
    client.write_points.return_value = True
    client_class.return_value = client
    coletor = ColetorOPC()

    assert coletor.registrar_heartbeat(
        cycle_seconds=12.5,
        equipment_count=126,
        measurement_count=31,
    )

    payload = client.write_points.call_args.args[0][0]
    assert payload['measurement'] == 'collector_heartbeat'
    assert payload['tags'] == {'service': 'mis-core-coletor'}
    assert payload['fields'] == {
        'alive': 1,
        'cycle_seconds': 12.5,
        'equipment_count': 126,
        'measurement_count': 31,
        'valid_tag_count': 0,
        'rejected_tag_count': 0,
        'no_read_tag_count': 0,
    }


@patch('influxdb.InfluxDBClient')
def test_registrar_heartbeat_recovers_after_write_failure(client_class):
    first = Mock()
    first.write_points.side_effect = RuntimeError('offline')
    second = Mock()
    second.write_points.return_value = True
    client_class.side_effect = [first, second]
    coletor = ColetorOPC()

    assert not coletor.registrar_heartbeat(
        cycle_seconds=1, equipment_count=1, measurement_count=1
    )
    assert coletor.registrar_heartbeat(
        cycle_seconds=2, equipment_count=2, measurement_count=2
    )
    assert client_class.call_count == 2

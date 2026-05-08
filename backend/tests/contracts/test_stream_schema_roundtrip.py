from shared.contracts.streams import QuerySubmittedV1, SCHEMA_VERSION_V1, redis_payload, parse_payload_json


def test_query_submitted_roundtrip():
    m = QuerySubmittedV1(
        schema_version=SCHEMA_VERSION_V1,
        correlation_id="c1",
        job_id="j1",
        command_id="cmd1",
        producer="t",
        query="hello",
        session_id="s1",
    )
    fields = redis_payload(m)
    back = parse_payload_json(fields, QuerySubmittedV1)
    assert isinstance(back, QuerySubmittedV1)
    assert back.query == "hello"
    assert back.job_id == "j1"

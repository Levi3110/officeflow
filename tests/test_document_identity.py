from synthetic_human.desktop import document_matches
from synthetic_human.models import Observation


def test_same_filename_in_another_run_is_not_the_target_document(tmp_path):
    current = tmp_path / "one" / "comparison.ods"
    target = tmp_path / "two" / "comparison.ods"
    observation = Observation(
        timestamp=0, application="LibreOffice", title="comparison.ods", document_uri=current.as_uri()
    )
    assert not document_matches(target, observation)
    assert document_matches(current, observation)


def test_missing_native_document_identity_cannot_authorize_edit(tmp_path):
    observation = Observation(timestamp=0, application="LibreOffice", title="comparison.ods")
    assert not document_matches(tmp_path / "comparison.ods", observation)

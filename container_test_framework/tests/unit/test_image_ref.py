"""Unit tests for Docker image-reference parsing (``ctf.engine.image_ref``).

The parser is the fix for the ``mysql`` vs ``mysql/mysql`` pull bug: it treats
``--image`` as a real Docker reference instead of fabricating a registry.
"""
import pytest

from ctf.engine.image_ref import ImageRef

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "image, default_tag, repository, name, tag, reference, container_name",
    [
        # official image, no tag -> default
        ("mysql", "latest", "mysql", "mysql", "latest", "mysql:latest", "mysql-latest"),
        # official image with explicit tag
        ("mysql:8.0", "latest", "mysql", "mysql", "8.0", "mysql:8.0", "mysql-8.0"),
        # namespaced image
        ("bitnami/mysql:8.0", "latest", "bitnami/mysql", "mysql", "8.0",
         "bitnami/mysql:8.0", "mysql-8.0"),
        # registry host WITH a port must not be mistaken for a tag
        ("reg.io:5000/team/app:1.2", "latest", "reg.io:5000/team/app", "app", "1.2",
         "reg.io:5000/team/app:1.2", "app-1.2"),
        # registry + namespace, no tag
        ("reg.io:5000/team/app", "latest", "reg.io:5000/team/app", "app", "latest",
         "reg.io:5000/team/app:latest", "app-latest"),
    ],
)
def test_parse_variants(image, default_tag, repository, name, tag, reference, container_name):
    ref = ImageRef.parse(image, default_tag)
    assert ref.repository == repository
    assert ref.name == name
    assert ref.tag == tag
    assert ref.reference == reference
    assert ref.container_name == container_name


def test_explicit_tag_in_reference_beats_default():
    ref = ImageRef.parse("mysql:5.7", default_tag="8.0")
    assert ref.tag == "5.7"
    assert ref.reference == "mysql:5.7"


def test_default_tag_used_when_reference_has_none():
    ref = ImageRef.parse("mysql", default_tag="8.0")
    assert ref.tag == "8.0"
    assert ref.reference == "mysql:8.0"


def test_digest_is_preserved_and_not_parsed_as_tag():
    ref = ImageRef.parse("mysql@sha256:abc123", default_tag="8.0")
    assert ref.repository == "mysql"
    assert ref.digest == "sha256:abc123"
    # a digest pins the image; reference uses @digest, not :tag
    assert ref.reference == "mysql@sha256:abc123"


@pytest.mark.edge
@pytest.mark.parametrize("bad", ["", "   ", None])
def test_empty_reference_raises(bad):
    with pytest.raises(ValueError):
        ImageRef.parse(bad)


@pytest.mark.edge
def test_reference_with_tag_but_no_repository_raises():
    # ":8.0" has a tag colon but no repository part
    with pytest.raises(ValueError, match="could not parse repository"):
        ImageRef.parse(":8.0")

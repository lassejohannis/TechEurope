"""Tests for ontology loader."""

from __future__ import annotations

from pathlib import Path

from server.ontology.loader import load_all, get_ontology_dir, load_yaml


def test_get_ontology_dir_finds_config():
    dirpath = get_ontology_dir()
    assert dirpath is not None, "Could not find config/ontologies directory"
    assert dirpath.is_dir()


def test_load_all_returns_yaml_files():
    loaded = load_all()
    assert len(loaded) >= 4
    assert "base.yaml" in loaded
    assert "hr.yaml" in loaded
    assert "sales.yaml" in loaded
    assert "enterprise.yaml" in loaded


def test_load_yaml_base_structure():
    dirpath = get_ontology_dir()
    assert dirpath is not None
    ontology = load_yaml(dirpath / "base.yaml")
    assert "entity_types" in ontology
    assert "edge_types" in ontology
    assert "person" in ontology["entity_types"]
    assert "organization" in ontology["entity_types"]


def test_load_yaml_hr_structure():
    dirpath = get_ontology_dir()
    assert dirpath is not None
    ontology = load_yaml(dirpath / "hr.yaml")
    assert "employee" in ontology.get("entity_types", {})
    assert "department" in ontology.get("entity_types", {})


def test_load_yaml_sales_structure():
    dirpath = get_ontology_dir()
    assert dirpath is not None
    ontology = load_yaml(dirpath / "sales.yaml")
    assert "customer" in ontology.get("entity_types", {})
    assert "product" in ontology.get("entity_types", {})


def test_all_yamls_have_valid_keys():
    loaded = load_all()
    dirpath = get_ontology_dir()
    assert dirpath is not None
    for name in loaded:
        ontology = load_yaml(dirpath / name)
        for key in (ontology.get("entity_types") or {}):
            assert isinstance(key, str), f"{name}: entity type key must be str"
        for key in (ontology.get("edge_types") or {}):
            assert isinstance(key, str), f"{name}: edge type key must be str"

"""Tests for TOML ↔ Markdown conversion."""

import tomllib

from youlab_server.storage.convert import (
    _finalize_section,
    _title_to_key,
    markdown_to_toml,
    toml_to_markdown,
)


class TestTomlToMarkdown:
    """Tests for toml_to_markdown conversion."""

    def test_basic_conversion(self):
        """Convert simple TOML to markdown."""
        toml_content = 'name = "Alice"\nrole = "Student"'
        result = toml_to_markdown(toml_content, "student")

        assert "---" in result
        assert "block: student" in result
        assert "## Name" in result
        assert "Alice" in result
        assert "## Role" in result
        assert "Student" in result

    def test_list_conversion(self):
        """Convert TOML list to markdown bullet points."""
        toml_content = 'strengths = ["Creativity", "Communication", "Leadership"]'
        result = toml_to_markdown(toml_content, "student")

        assert "## Strengths" in result
        assert "- Creativity" in result
        assert "- Communication" in result
        assert "- Leadership" in result

    def test_multiline_string(self):
        """Convert multi-line TOML string to markdown paragraph."""
        toml_content = 'background = "First paragraph.\\n\\nSecond paragraph."'
        result = toml_to_markdown(toml_content, "student")

        assert "## Background" in result
        assert "First paragraph.\n\nSecond paragraph." in result

    def test_boolean_conversion(self):
        """Convert boolean values to Yes/No."""
        toml_content = "active = true\ncompleted = false"
        result = toml_to_markdown(toml_content, "status")

        assert "Yes" in result
        assert "No" in result

    def test_numeric_conversion(self):
        """Convert numeric values to string."""
        toml_content = "age = 25\nscore = 95.5"
        result = toml_to_markdown(toml_content, "student")

        assert "25" in result
        assert "95.5" in result

    def test_snake_case_to_title_case(self):
        """Convert snake_case keys to Title Case headers."""
        toml_content = 'engagement_strategy = "Test"'
        result = toml_to_markdown(toml_content, "student")

        assert "## Engagement Strategy" in result

    def test_invalid_toml_returns_code_block(self):
        """Invalid TOML returns content in code block with error flag."""
        invalid_toml = "this is not valid toml {"
        result = toml_to_markdown(invalid_toml, "student")

        assert "error: invalid_toml" in result
        assert "```toml" in result
        assert invalid_toml in result


class TestMarkdownToToml:
    """Tests for markdown_to_toml conversion."""

    def test_basic_conversion(self):
        """Convert simple markdown to TOML."""
        markdown = """---
block: student
---

## Name
Alice

## Role
Student
"""
        toml_str, metadata = markdown_to_toml(markdown)
        data = tomllib.loads(toml_str)

        assert metadata["block"] == "student"
        assert data["name"] == "Alice"
        assert data["role"] == "Student"

    def test_list_conversion(self):
        """Convert markdown bullet points to TOML list."""
        markdown = """---
block: student
---

## Strengths
- Creativity
- Communication
- Leadership
"""
        toml_str, _ = markdown_to_toml(markdown)
        data = tomllib.loads(toml_str)

        assert data["strengths"] == ["Creativity", "Communication", "Leadership"]

    def test_multiline_content(self):
        """Convert multi-paragraph markdown to TOML string."""
        markdown = """---
block: student
---

## Background
First paragraph.

Second paragraph.
"""
        toml_str, _ = markdown_to_toml(markdown)
        data = tomllib.loads(toml_str)

        assert "First paragraph." in data["background"]
        assert "Second paragraph." in data["background"]

    def test_title_case_to_snake_case(self):
        """Convert Title Case headers to snake_case keys."""
        markdown = """---
block: student
---

## Engagement Strategy
Test strategy
"""
        toml_str, _ = markdown_to_toml(markdown)
        data = tomllib.loads(toml_str)

        assert "engagement_strategy" in data

    def test_not_set_marker_ignored(self):
        """Ignore *(not set)* marker in content."""
        markdown = """---
block: student
---

## Name
Alice

## Role
*(not set)*
"""
        toml_str, _ = markdown_to_toml(markdown)
        data = tomllib.loads(toml_str)

        assert data["name"] == "Alice"
        assert data["role"] == ""

    def test_no_frontmatter(self):
        """Handle markdown without frontmatter."""
        markdown = """## Name
Alice

## Role
Student
"""
        toml_str, metadata = markdown_to_toml(markdown)
        data = tomllib.loads(toml_str)

        assert metadata == {}
        assert data["name"] == "Alice"
        assert data["role"] == "Student"


class TestRoundTrip:
    """Tests for round-trip conversion (TOML → Markdown → TOML)."""

    def test_simple_roundtrip(self):
        """Simple string fields survive round-trip."""
        original_toml = 'name = "Alice"\nrole = "Student"'
        original_data = tomllib.loads(original_toml)

        markdown = toml_to_markdown(original_toml, "student")
        roundtrip_toml, _ = markdown_to_toml(markdown)
        roundtrip_data = tomllib.loads(roundtrip_toml)

        assert roundtrip_data["name"] == original_data["name"]
        assert roundtrip_data["role"] == original_data["role"]

    def test_list_roundtrip(self):
        """List fields survive round-trip."""
        original_toml = 'strengths = ["Creativity", "Communication"]'
        original_data = tomllib.loads(original_toml)

        markdown = toml_to_markdown(original_toml, "student")
        roundtrip_toml, _ = markdown_to_toml(markdown)
        roundtrip_data = tomllib.loads(roundtrip_toml)

        assert roundtrip_data["strengths"] == original_data["strengths"]

    def test_complex_roundtrip(self):
        """Complex data structure survives round-trip."""
        original_toml = """name = "Alice"
background = "A detailed background."
strengths = ["Creativity", "Communication", "Leadership"]
engagement_strategy = "Collaborative approach"
"""
        original_data = tomllib.loads(original_toml)

        markdown = toml_to_markdown(original_toml, "student")
        roundtrip_toml, metadata = markdown_to_toml(markdown)
        roundtrip_data = tomllib.loads(roundtrip_toml)

        assert metadata["block"] == "student"
        assert roundtrip_data["name"] == original_data["name"]
        assert roundtrip_data["background"] == original_data["background"]
        assert roundtrip_data["strengths"] == original_data["strengths"]
        assert roundtrip_data["engagement_strategy"] == original_data["engagement_strategy"]


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_title_to_key_simple(self):
        """Convert simple title to key."""
        assert _title_to_key("Name") == "name"
        assert _title_to_key("Role") == "role"

    def test_title_to_key_multi_word(self):
        """Convert multi-word title to snake_case."""
        assert _title_to_key("Engagement Strategy") == "engagement_strategy"
        assert _title_to_key("Background Info") == "background_info"

    def test_title_to_key_extra_spaces(self):
        """Handle extra spaces in title."""
        assert _title_to_key("Multiple   Spaces") == "multiple_spaces"

    def test_finalize_section_list(self):
        """Finalize list content."""
        content = ["Item 1", "Item 2", "Item 3"]
        result = _finalize_section(content, is_list=True)
        assert result == content

    def test_finalize_section_string(self):
        """Finalize string content."""
        content = ["Line 1", "Line 2"]
        result = _finalize_section(content, is_list=False)
        assert result == "Line 1\nLine 2"

    def test_finalize_section_empty(self):
        """Finalize empty content."""
        result = _finalize_section([], is_list=False)
        assert result == ""

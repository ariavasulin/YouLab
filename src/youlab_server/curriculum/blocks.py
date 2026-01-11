"""
Dynamic memory block generation from TOML schemas.

This module generates Pydantic model classes at runtime based on
BlockSchema definitions from course configurations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, create_model

from youlab_server.curriculum.schema import BlockSchema, FieldSchema, FieldType


def _get_python_type(field: FieldSchema) -> Any:
    """Map FieldType to Python type annotation."""
    type_map: dict[FieldType, Any] = {
        FieldType.STRING: str,
        FieldType.INT: int,
        FieldType.FLOAT: float,
        FieldType.BOOL: bool,
        FieldType.LIST: list[str],
        FieldType.DATETIME: datetime | None,
    }
    return type_map.get(field.type, str)


def _get_default_value(field: FieldSchema) -> Any:
    """Get default value for a field."""
    if field.default is not None:
        return field.default

    # Type-specific defaults
    defaults: dict[FieldType, Any] = {
        FieldType.STRING: "",
        FieldType.INT: 0,
        FieldType.FLOAT: 0.0,
        FieldType.BOOL: False,
        FieldType.LIST: [],
        FieldType.DATETIME: None,
    }
    return defaults.get(field.type, "")


class DynamicBlock(BaseModel):
    """Base class for dynamically generated blocks."""

    def to_memory_string(self) -> str:
        """
        Serialize block to memory string format.

        Format:
        ```
        field_name: value
        field_name:
        - item1
        - item2
        ```
        """
        lines: list[str] = []
        for field_name, value in self.model_dump().items():
            if isinstance(value, list):
                lines.append(f"{field_name}:")
                lines.extend(f"- {item}" for item in value)
            elif value:  # Only include non-empty values
                lines.append(f"{field_name}: {value}")
        return "\n".join(lines)

    @classmethod
    def from_memory_string(cls, content: str) -> DynamicBlock:
        """
        Parse memory string back into block instance.

        This is a best-effort parser that handles the format from to_memory_string().
        """
        data: dict[str, Any] = {}
        current_field: str | None = None
        current_list: list[str] | None = None

        for raw_line in content.split("\n"):
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("- "):
                # List item
                if current_list is not None:
                    current_list.append(line[2:])
            elif ":" in line:
                # Field definition
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()

                # Save previous list if any
                if current_field and current_list is not None:
                    data[current_field] = current_list

                if value:
                    # Simple field with value
                    data[key] = value
                    current_field = None
                    current_list = None
                else:
                    # Start of list field
                    current_field = key
                    current_list = []

        # Save final list
        if current_field and current_list is not None:
            data[current_field] = current_list

        return cls(**data)


def create_block_model(
    block_name: str,
    schema: BlockSchema,
) -> type[DynamicBlock]:
    """
    Create a Pydantic model class from a BlockSchema.

    Args:
        block_name: Name of the block (e.g., "persona", "human")
        schema: BlockSchema defining the fields

    Returns:
        A new Pydantic model class

    Example:
        >>> schema = BlockSchema(
        ...     label="persona",
        ...     fields={"name": FieldSchema(type=FieldType.STRING, default="Bot")}
        ... )
        >>> PersonaBlock = create_block_model("persona", schema)
        >>> block = PersonaBlock(name="MyBot")
        >>> block.to_memory_string()
        "name: MyBot"

    """
    field_definitions: dict[str, Any] = {}

    for field_name, field_schema in schema.fields.items():
        python_type = _get_python_type(field_schema)
        default = _get_default_value(field_schema)

        # Handle list defaults properly (use factory)
        if field_schema.type == FieldType.LIST:
            default_list = default if isinstance(default, list) else []
            field_definitions[field_name] = (
                python_type,
                Field(default_factory=lambda d=default_list: list(d)),
            )
        else:
            field_definitions[field_name] = (python_type, Field(default=default))

    # Create model class name
    class_name = f"{block_name.title().replace('-', '').replace('_', '')}Block"

    # Create the model
    return create_model(
        class_name,
        __base__=DynamicBlock,
        **field_definitions,
    )


def create_block_registry(
    blocks: dict[str, BlockSchema],
) -> dict[str, type[DynamicBlock]]:
    """
    Create a registry of block model classes from course block schemas.

    Args:
        blocks: Dict of block_name -> BlockSchema from CourseConfig

    Returns:
        Dict of block_name -> model class

    """
    registry: dict[str, type[DynamicBlock]] = {}

    for block_name, schema in blocks.items():
        registry[block_name] = create_block_model(block_name, schema)

    return registry

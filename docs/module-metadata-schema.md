# YouLab Module Metadata Schema

Modules are OpenWebUI models with additional `youlab_module` metadata that enables course-based navigation in the YouLab sidebar.

## Overview

When a model includes the `youlab_module` metadata field, it appears in the "Modules" section of the sidebar rather than the standard model list. This allows course-structured navigation with status indicators.

## Schema Definition

### TypeScript Interface

```typescript
interface YouLabModuleMeta {
  course_id: string;           // Course identifier (e.g., "college-essay")
  module_index: number;        // Display order (0-based)
  status?: 'locked' | 'available' | 'in_progress' | 'completed';
  welcome_message?: string;    // Agent-speaks-first message
  unlock_criteria?: {          // Future: automatic unlocking
    previous_module?: string;  // Module ID that must be completed
    min_interactions?: number; // Minimum conversation turns
  };
}

interface ModelMeta {
  // Standard OpenWebUI model meta fields
  profile_image_url?: string;
  description?: string;
  suggestion_prompts?: Array<{content: string, title: [string, string]}>;
  capabilities?: object;
  toolIds?: string[];
  knowledge?: object[];

  // YouLab extension
  youlab_module?: YouLabModuleMeta;
}
```

### JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "youlab_module": {
      "type": "object",
      "required": ["course_id", "module_index"],
      "properties": {
        "course_id": {
          "type": "string",
          "description": "Unique identifier for the course this module belongs to"
        },
        "module_index": {
          "type": "integer",
          "minimum": 0,
          "description": "Display order within the course (0-based)"
        },
        "status": {
          "type": "string",
          "enum": ["locked", "available", "in_progress", "completed"],
          "default": "available",
          "description": "Current module status for the user"
        },
        "welcome_message": {
          "type": "string",
          "description": "Initial message the agent sends when starting a conversation"
        },
        "unlock_criteria": {
          "type": "object",
          "properties": {
            "previous_module": {
              "type": "string",
              "description": "ID of module that must be completed first"
            },
            "min_interactions": {
              "type": "integer",
              "minimum": 1,
              "description": "Minimum conversation turns required"
            }
          }
        }
      }
    }
  }
}
```

## Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `course_id` | string | Yes | Identifier linking modules to a course (e.g., "college-essay") |
| `module_index` | number | Yes | Sort order within the course (0 = first) |
| `status` | enum | No | Visual status indicator. Default: "available" |
| `welcome_message` | string | No | Agent's first message when conversation starts |
| `unlock_criteria` | object | No | Conditions for unlocking (future feature) |

### Status Values

| Status | Icon | Color | Description |
|--------|------|-------|-------------|
| `locked` | Lock | Gray | Module not yet accessible |
| `available` | None | Blue | Ready to start |
| `in_progress` | Clock | Yellow | Currently working on |
| `completed` | Checkmark | Green | Successfully finished |

## Creating a Module

### Via OpenWebUI Admin Panel

1. Navigate to **Admin Panel > Models**
2. Click **Add Model**
3. Set the base model (e.g., `youlab-letta-pipe`)
4. In the **Meta** JSON field, add:

```json
{
  "profile_image_url": "/static/modules/intro.png",
  "description": "Learn what makes a compelling college essay opening",
  "youlab_module": {
    "course_id": "college-essay",
    "module_index": 0,
    "status": "available",
    "welcome_message": "Hi! I'm excited to help you craft the perfect opening for your college essay. What school are you applying to?"
  }
}
```

### Via API

```bash
curl -X POST "http://localhost:8080/api/models" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "college-essay-intro",
    "name": "First Impressions",
    "base_model_id": "youlab-letta-pipe",
    "meta": {
      "profile_image_url": "/static/modules/intro.png",
      "description": "Learn what makes a compelling college essay opening",
      "youlab_module": {
        "course_id": "college-essay",
        "module_index": 0,
        "status": "available",
        "welcome_message": "Hi! I'\''m excited to help you craft the perfect opening for your college essay."
      }
    }
  }'
```

## Example: College Essay Course

A complete course with 5 modules:

```json
[
  {
    "id": "college-essay-intro",
    "name": "First Impressions",
    "meta": {
      "description": "Craft a compelling opening hook",
      "youlab_module": {
        "course_id": "college-essay",
        "module_index": 0,
        "status": "available"
      }
    }
  },
  {
    "id": "college-essay-story",
    "name": "Your Story",
    "meta": {
      "description": "Find the story only you can tell",
      "youlab_module": {
        "course_id": "college-essay",
        "module_index": 1,
        "status": "locked",
        "unlock_criteria": {
          "previous_module": "college-essay-intro"
        }
      }
    }
  },
  {
    "id": "college-essay-voice",
    "name": "Finding Your Voice",
    "meta": {
      "description": "Develop authentic writing style",
      "youlab_module": {
        "course_id": "college-essay",
        "module_index": 2,
        "status": "locked"
      }
    }
  },
  {
    "id": "college-essay-structure",
    "name": "Structure & Flow",
    "meta": {
      "description": "Organize your essay effectively",
      "youlab_module": {
        "course_id": "college-essay",
        "module_index": 3,
        "status": "locked"
      }
    }
  },
  {
    "id": "college-essay-polish",
    "name": "Final Polish",
    "meta": {
      "description": "Refine and perfect your essay",
      "youlab_module": {
        "course_id": "college-essay",
        "module_index": 4,
        "status": "locked"
      }
    }
  }
]
```

## Implementation Notes

### Current Limitations (Phase A)

- **Static status**: Module status is stored in model metadata, not per-user. All users see the same status.
- **No automatic unlocking**: `unlock_criteria` is defined but not enforced. Unlocking requires manual status updates.
- **No progression tracking**: Per-user progression will be added in Phase B via agent `journey` memory block.

### Frontend Display

Modules are filtered and displayed by `ModuleList.svelte`:

```typescript
$: modules = $models
  .filter(model => model.info?.meta?.youlab_module)
  .map(model => ({
    id: model.id,
    name: model.name,
    description: model.info?.meta?.description,
    status: model.info?.meta?.youlab_module?.status ?? 'available',
    icon_url: model.info?.meta?.profile_image_url,
    module_index: model.info?.meta?.youlab_module?.module_index ?? 0
  }))
  .sort((a, b) => a.module_index - b.module_index);
```

### Future Enhancements

- **Per-user status**: Read status from user's agent memory (`journey` block)
- **Automatic unlocking**: Evaluate `unlock_criteria` against user progress
- **Progress persistence**: Track module interactions via Honcho
- **Multi-course support**: Filter modules by active course context

## Related Documentation

- [Configuration Schema](config-schema.md) - Course TOML configuration
- [Agent System](Agent-System.md) - Letta agent architecture
- [Memory System](Memory-System.md) - Journey block for progression

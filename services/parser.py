import yaml


def parse_skill_md(content: str) -> dict:
    """Parse SKILL.md file content.

    Returns: {"name": str, "description": str, "body": str, "frontmatter": dict}
    Raises ValueError if frontmatter missing or name/description absent.
    """
    if not content.strip():
        raise ValueError("SKILL.md content is empty")

    # Split on --- markers to extract frontmatter
    lines = content.split("\n")
    if not lines[0].strip() == "---":
        raise ValueError("SKILL.md must start with YAML frontmatter (---)")

    # Find closing ---
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        raise ValueError("SKILL.md frontmatter missing closing ---")

    yaml_text = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1:])

    try:
        frontmatter = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML frontmatter: {e}")

    if not isinstance(frontmatter, dict):
        raise ValueError("YAML frontmatter must be a mapping")

    name = frontmatter.get("name", "").strip()
    description = frontmatter.get("description", "").strip()

    if not name:
        raise ValueError("Missing required field 'name' in SKILL.md frontmatter")
    if not description:
        raise ValueError("Missing required field 'description' in SKILL.md frontmatter")

    return {
        "name": name,
        "description": description,
        "body": body,
        "frontmatter": frontmatter,
    }

"""Static literal-path scanner used by the engine-boundary contract test."""

import ast
import posixpath

FORBIDDEN_REFERENCES = ("logs/", "docs/", "~/Documents/papers", "Documents/papers")
_UNKNOWN = object()


class _StaticPath(str):
    pass


def _qualified_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _qualified_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else None
    return None


def _aliases(tree):
    result = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result[alias.asname or alias.name.split(".", 1)[0]] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                result[alias.asname or alias.name] = f"{module}.{alias.name}"
    return result


def _canonical_name(node, aliases):
    name = _qualified_name(node)
    if not name:
        return None
    head, *tail = name.split(".")
    return ".".join([aliases.get(head, head), *tail])


def _join(parts):
    return posixpath.join(*(part.replace("\\", "/") for part in parts))


def _static_value(node, aliases):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = [_static_value(value, aliases) for value in node.values]
        return _StaticPath("".join(parts)) if all(isinstance(part, str) for part in parts) else _UNKNOWN
    if isinstance(node, ast.FormattedValue):
        value = _static_value(node.value, aliases)
        return value if isinstance(value, (str, int, float)) else _UNKNOWN
    if isinstance(node, ast.BinOp):
        left = _static_value(node.left, aliases)
        right = _static_value(node.right, aliases)
        if isinstance(node.op, ast.Add) and isinstance(left, str) and isinstance(right, str):
            return _StaticPath(left + right)
        if isinstance(node.op, ast.Div) and isinstance(left, _StaticPath) and isinstance(right, str):
            return _StaticPath(_join((left, right)))
        return _UNKNOWN
    if not isinstance(node, ast.Call):
        return _UNKNOWN
    name = _canonical_name(node.func, aliases)
    constructors = {
        "pathlib.Path",
        "pathlib.PurePath",
        "pathlib.PurePosixPath",
        "pathlib.PureWindowsPath",
    }
    if name in constructors:
        parts = [_static_value(argument, aliases) for argument in node.args]
        if not node.keywords and all(isinstance(part, str) for part in parts):
            return _StaticPath(_join(parts) if parts else ".")
        return _UNKNOWN
    if name in {"os.path.join", "posixpath.join", "ntpath.join"}:
        parts = [_static_value(argument, aliases) for argument in node.args]
        if node.args and not node.keywords and all(isinstance(part, str) for part in parts):
            return _StaticPath(_join(parts))
        return _UNKNOWN
    if isinstance(node.func, ast.Attribute):
        base = _static_value(node.func.value, aliases)
        if node.func.attr == "joinpath" and isinstance(base, _StaticPath):
            parts = [_static_value(argument, aliases) for argument in node.args]
            if not node.keywords and all(isinstance(part, str) for part in parts):
                return _StaticPath(_join((base, *parts)))
        if node.func.attr == "format" and isinstance(base, str):
            values = [_static_value(argument, aliases) for argument in node.args]
            if not node.keywords and all(value is not _UNKNOWN for value in values):
                try:
                    return _StaticPath(base.format(*values))
                except (IndexError, KeyError, TypeError, ValueError):
                    return _UNKNOWN
    return _UNKNOWN


def _literal_path_context(node, parents, aliases):
    parent = parents.get(node)
    if isinstance(parent, (ast.Assign, ast.AnnAssign, ast.NamedExpr, ast.Return)):
        return getattr(parent, "value", None) is node
    return (
        isinstance(parent, ast.Call)
        and bool(parent.args)
        and parent.args[0] is node
        and _canonical_name(parent.func, aliases) in {"open", "io.open"}
    )


def scan_source(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    aliases = _aliases(tree)
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    values = []
    for node in ast.walk(tree):
        value = _static_value(node, aliases)
        if isinstance(value, _StaticPath):
            values.append(value)
        elif (
            isinstance(value, str)
            and value == value.strip()
            and not any(character.isspace() for character in value)
            and _literal_path_context(node, parents, aliases)
        ):
            values.append(value)
    return [
        pattern
        for pattern in FORBIDDEN_REFERENCES
        if any(pattern in value.replace("\\", "/") for value in values)
    ]

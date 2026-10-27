"""
Personalized Learning Roadmap Service
Pure business-logic engine for deterministic roadmap generation,
prerequisite validation, and progress progression.
Owned by: Arsh (FastAPI Backend Architecture)
"""

import re
from typing import List, Dict, Any, Set, Optional


SUPPORTED_SUBJECTS = {
    "subj_python": "Python Programming",
    "subj_js": "JavaScript & Web Fundamentals",
    "subj_react": "React & Modern UI Development",
    "subj_system_design": "Distributed System Design"
}

# Standard catalog of learning modules for Python
PYTHON_CATALOG: Dict[str, Dict[str, Any]] = {
    "types": {
        "id": "mod_py_types",
        "title": "Python Data Types, Variables & Memory",
        "description": "Understand Python primitives, mutability, pass-by-assignment semantics, and object identity (id/is).",
        "subject_id": "subj_python",
        "difficulty": "Beginner",
        "estimated_minutes": 25,
        "prerequisite_module_ids": [],
        "keywords": ["type", "types", "variable", "variables", "mutability", "memory", "int", "string", "bool"]
    },
    "collections": {
        "id": "mod_py_collections",
        "title": "Lists, Tuples, Dictionaries & Slicing",
        "description": "Master iterable sequences, dictionary hashing, set operations, and slicing patterns [start:stop:step].",
        "subject_id": "subj_python",
        "difficulty": "Beginner",
        "estimated_minutes": 30,
        "prerequisite_module_ids": ["mod_py_types"],
        "keywords": ["list", "tuple", "dict", "dictionary", "set", "slice", "slicing", "collection", "collections"]
    },
    "functions": {
        "id": "mod_py_functions",
        "title": "Functions, Scope (LEGB) & Closures",
        "description": "Deep dive into function definitions, *args/**kwargs, default mutable traps, LEGB scope, and closures.",
        "subject_id": "subj_python",
        "difficulty": "Intermediate",
        "estimated_minutes": 35,
        "prerequisite_module_ids": ["mod_py_collections"],
        "keywords": ["function", "functions", "scope", "legb", "closure", "closures", "args", "kwargs"]
    },
    "comprehensions": {
        "id": "mod_py_comprehensions",
        "title": "Comprehensions & Functional Idioms",
        "description": "Write idiomatic list, dict, and set comprehensions alongside map, filter, and lambda expressions.",
        "subject_id": "subj_python",
        "difficulty": "Intermediate",
        "estimated_minutes": 30,
        "prerequisite_module_ids": ["mod_py_functions"],
        "keywords": ["comprehension", "comprehensions", "lambda", "map", "filter", "iterator"]
    },
    "oop": {
        "id": "mod_py_oop",
        "title": "Object-Oriented Programming & Dunder Methods",
        "description": "Classes, inheritance, polymorphism, encapsulation, super(), and essential magic methods (__repr__, __eq__).",
        "subject_id": "subj_python",
        "difficulty": "Intermediate",
        "estimated_minutes": 40,
        "prerequisite_module_ids": ["mod_py_functions"],
        "keywords": ["oop", "class", "classes", "inheritance", "dunder", "object", "self"]
    },
    "generators": {
        "id": "mod_py_generators",
        "title": "Generators, Iterators & Memory Streaming",
        "description": "Implement lazy evaluation using the yield keyword, generator expressions, and custom iterator protocols.",
        "subject_id": "subj_python",
        "difficulty": "Advanced",
        "estimated_minutes": 45,
        "prerequisite_module_ids": ["mod_py_comprehensions"],
        "keywords": ["generator", "generators", "yield", "iterator", "stream", "lazy"]
    },
    "decorators": {
        "id": "mod_py_decorators",
        "title": "Decorators & Context Managers",
        "description": "Build parameterized decorators, preserve metadata with functools.wraps, and implement with-statements.",
        "subject_id": "subj_python",
        "difficulty": "Advanced",
        "estimated_minutes": 45,
        "prerequisite_module_ids": ["mod_py_functions"],
        "keywords": ["decorator", "decorators", "context manager", "with", "wraps"]
    },
    "async": {
        "id": "mod_py_async",
        "title": "Asynchronous Programming with AsyncIO",
        "description": "Event loops, coroutines, async/await syntax, Task scheduling, and concurrent network I/O.",
        "subject_id": "subj_python",
        "difficulty": "Advanced",
        "estimated_minutes": 50,
        "prerequisite_module_ids": ["mod_py_generators"],
        "keywords": ["async", "asyncio", "await", "coroutine", "concurrency", "event loop"]
    }
}


class SubjectCatalogComingSoonError(ValueError):
    """Raised when a subject is recognized but its curriculum catalog is not yet implemented."""
    pass


SUBJECT_CATALOGS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "subj_python": PYTHON_CATALOG
}


def validate_catalog_integrity(catalog: Dict[str, Dict[str, Any]]) -> None:
    """
    Validates structural integrity of a curriculum catalog:
    - All prerequisite IDs exist in catalog.
    - No module depends on itself.
    - No circular dependencies exist (cycle detection via DFS).
    Raises ValueError with a clear, descriptive message if any violation is found.
    """
    all_module_ids = {mod["id"] for mod in catalog.values()}

    for key, mod in catalog.items():
        mod_id = mod["id"]
        prereqs = mod.get("prerequisite_module_ids", [])
        for p_id in prereqs:
            if p_id not in all_module_ids:
                raise ValueError(
                    f"Catalog integrity error: Module '{mod_id}' references non-existent prerequisite '{p_id}'."
                )
            if p_id == mod_id:
                raise ValueError(
                    f"Catalog integrity error: Self-referential prerequisite detected in module '{mod_id}'."
                )

    # Cycle detection using DFS coloring (0: unvisited, 1: visiting, 2: visited)
    adj: Dict[str, List[str]] = {
        mod["id"]: list(mod.get("prerequisite_module_ids", []))
        for mod in catalog.values()
    }
    visited: Dict[str, int] = {m_id: 0 for m_id in all_module_ids}

    def dfs(curr: str, path: List[str]):
        visited[curr] = 1
        for neighbor in adj.get(curr, []):
            if visited.get(neighbor) == 1:
                cycle_str = " -> ".join(path + [neighbor])
                raise ValueError(
                    f"Catalog integrity error: Circular dependency detected in prerequisite graph: {cycle_str}."
                )
            elif visited.get(neighbor) == 0:
                dfs(neighbor, path + [neighbor])
        visited[curr] = 2

    for m_id in all_module_ids:
        if visited[m_id] == 0:
            dfs(m_id, [m_id])


# Validate standard catalog at module import
validate_catalog_integrity(PYTHON_CATALOG)


def _match_topic_to_module(
    topic_text: str, catalog: Dict[str, Dict[str, Any]] = PYTHON_CATALOG
) -> Optional[Dict[str, Any]]:
    """Matches a weakness topic string to a catalog module using keyword scoring heuristics."""
    clean = topic_text.lower().strip()
    words = set(re.findall(r"\w+", clean))
    best_match = None
    best_score = 0
    for key, mod in catalog.items():
        score = 0
        for kw in mod["keywords"]:
            if kw in words:
                score += len(kw) * 2
            elif kw in clean:
                score += len(kw)
        if score > best_score:
            best_score = score
            best_match = mod
    return best_match if best_score > 0 else None


def calculate_overall_progress(modules: List[Dict[str, Any]]) -> float:
    """Calculates average completion percentage across all modules in the roadmap."""
    if not modules:
        return 0.0
    total = sum(float(m.get("completion_percentage", 0.0)) for m in modules)
    return round(total / len(modules), 1)


def validate_module_prerequisites(module: Dict[str, Any], completed_module_ids: Set[str]) -> bool:
    """Returns True if all prerequisite modules for the given module have been completed."""
    prereqs = module.get("prerequisite_module_ids", [])
    if not prereqs:
        return True
    return all(prereq_id in completed_module_ids for prereq_id in prereqs)


def update_module_lock_statuses(
    modules: List[Dict[str, Any]], completed_module_ids: Set[str]
) -> List[Dict[str, Any]]:
    """
    Updates status and lock state for each module based on completed prerequisites:
    - If module_id in completed_module_ids: 'completed', completion_percentage = 100.0
    - If all prerequisites satisfied: 'unlocked' (or 'in_progress' if percentage > 0)
    - If prerequisites not satisfied: 'locked', completion_percentage = 0.0
    """
    updated: List[Dict[str, Any]] = []
    
    for m in modules:
        m_copy = dict(m)
        m_id = m_copy["id"]
        
        if m_id in completed_module_ids:
            m_copy["status"] = "completed"
            m_copy["completion_percentage"] = 100.0
        elif validate_module_prerequisites(m_copy, completed_module_ids):
            current_pct = float(m_copy.get("completion_percentage", 0.0))
            if current_pct > 0.0:
                m_copy["status"] = "in_progress"
            else:
                m_copy["status"] = "unlocked"
                m_copy["completion_percentage"] = 0.0
        else:
            m_copy["status"] = "locked"
            m_copy["completion_percentage"] = 0.0
            
        updated.append(m_copy)
        
    return updated


def validate_module_completion(
    module_id: str, modules: List[Dict[str, Any]], completed_module_ids: Set[str]
) -> bool:
    """Validates that a module exists and all its prerequisites are satisfied before marking it completed."""
    target = next((m for m in modules if m["id"] == module_id), None)
    if not target:
        raise ValueError(f"Module '{module_id}' not found in roadmap.")
    
    if not validate_module_prerequisites(target, completed_module_ids):
        missing = [p for p in target.get("prerequisite_module_ids", []) if p not in completed_module_ids]
        raise ValueError(
            f"Cannot complete module '{module_id}'. Unmet prerequisites: {', '.join(missing)}."
        )
    return True


def validate_progress_transition(
    current_status: str, new_status: str, current_percentage: float, new_percentage: float
) -> bool:
    """
    Validates state machine transitions for module progress:
    - Status must be valid: 'locked', 'unlocked', 'in_progress', 'completed'
    - Percentage must be between 0.0 and 100.0
    - Locked modules cannot transition directly to in_progress or completed
    - Locked modules cannot have progress > 0.0
    - Completed modules must have 100.0% completion
    - Completed modules cannot be reset to locked
    - Progress percentage cannot decrease
    """
    valid_statuses = {"locked", "unlocked", "in_progress", "completed"}
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status '{new_status}'. Must be one of {valid_statuses}.")
    
    if not (0.0 <= new_percentage <= 100.0):
        raise ValueError(f"Invalid completion percentage {new_percentage}. Must be between 0.0 and 100.0.")
    
    if current_status == "locked" and new_status in ("in_progress", "completed"):
        raise ValueError("Cannot transition a locked module directly to in_progress or completed.")
    
    if new_status == "locked" and new_percentage > 0.0:
        raise ValueError("Locked module cannot have progress greater than 0%.")
        
    if new_status == "completed" and new_percentage < 100.0:
        raise ValueError("Completed module must have exactly 100% completion.")
        
    if current_status == "completed" and new_status == "locked":
        raise ValueError("Completed module cannot be reset to locked.")
        
    if new_percentage < current_percentage:
        raise ValueError(f"Progress percentage cannot decrease from {current_percentage}% to {new_percentage}%.")
        
    return True


def build_deterministic_roadmap(
    subject_id: str,
    weaknesses: Optional[List[str]] = None,
    user_id: str = "default_user",
    completed_module_ids: Optional[Set[str]] = None
) -> Dict[str, Any]:
    """
    Builds a personalized, deterministic learning roadmap based on assessment diagnostic weaknesses.
    - If subject is not supported, raises ValueError.
    - If weaknesses are empty or None, builds foundational core curriculum.
    - Deduplicates weaknesses while preserving priority order.
    - Orders modules by difficulty and topological prerequisite dependency.
    """
    if subject_id not in SUPPORTED_SUBJECTS:
        raise ValueError(
            f"Unsupported subject '{subject_id}'. Supported subjects: {', '.join(sorted(SUPPORTED_SUBJECTS.keys()))}."
        )

    if subject_id not in SUBJECT_CATALOGS:
        raise SubjectCatalogComingSoonError("Roadmaps for this subject are coming soon.")

    catalog = SUBJECT_CATALOGS[subject_id]
    validate_catalog_integrity(catalog)

    completed = completed_module_ids or set()
    subject_title = SUPPORTED_SUBJECTS[subject_id]
    selected_module_keys: List[str] = []

    # 1. Deduplicate weakness topics while preserving order
    clean_weaknesses: List[str] = []
    seen_weaknesses: Set[str] = set()
    for w in (weaknesses or []):
        cleaned = w.strip()
        if cleaned and cleaned.lower() not in seen_weaknesses:
            seen_weaknesses.add(cleaned.lower())
            clean_weaknesses.append(cleaned)

    # 2. Select targeted modules from catalog based on weaknesses
    for w in clean_weaknesses:
        match = _match_topic_to_module(w, catalog)
        if match:
            # Find key in catalog
            for k, mod in catalog.items():
                if mod["id"] == match["id"] and k not in selected_module_keys:
                    selected_module_keys.append(k)

    # 3. Always ensure foundational modules are present to satisfy prerequisites
    if not selected_module_keys:
        # Default foundational roadmap (first 5 modules of catalog)
        selected_module_keys = list(catalog.keys())[:5]
    else:
        # If advanced modules selected, prepend missing prerequisites iteratively
        all_needed_keys = set(selected_module_keys)
        changed = True
        while changed:
            changed = False
            for key in list(all_needed_keys):
                mod_prereqs = catalog[key].get("prerequisite_module_ids", [])
                for p_id in mod_prereqs:
                    p_key = next((k for k, v in catalog.items() if v["id"] == p_id), None)
                    if p_key and p_key not in all_needed_keys:
                        all_needed_keys.add(p_key)
                        changed = True
        
        # Order keys according to the catalog canonical progression
        canonical_order = list(catalog.keys())
        selected_module_keys = [k for k in canonical_order if k in all_needed_keys]

    # 4. Construct raw module objects
    modules: List[Dict[str, Any]] = []
    for key in selected_module_keys:
        template = catalog[key]
        modules.append({
            "id": template["id"],
            "title": template["title"],
            "description": template["description"],
            "subject_id": subject_id,
            "difficulty": template["difficulty"],
            "estimated_minutes": template["estimated_minutes"],
            "prerequisite_module_ids": list(template["prerequisite_module_ids"]),
            "status": "locked",
            "completion_percentage": 0.0
        })

    # 5. Apply locking / unlocking state machine based on completed prerequisites
    modules = update_module_lock_statuses(modules, completed)

    # If nothing is completed, unlock the very first root module (having no prerequisites)
    if not completed and modules:
        for m in modules:
            if not m["prerequisite_module_ids"]:
                m["status"] = "unlocked"
                break

    # 6. Calculate overall progress percentage
    overall_progress = calculate_overall_progress(modules)

    roadmap_id = f"rdm_{subject_id.replace('subj_', '')}_{user_id}"
    
    desc = (
        f"Targeted learning path focusing on {len(clean_weaknesses)} diagnostic assessment area(s)."
        if clean_weaknesses
        else f"Comprehensive foundational learning path for {subject_title}."
    )

    return {
        "id": roadmap_id,
        "user_id": user_id,
        "subject_id": subject_id,
        "title": f"Personalized {subject_title} Roadmap",
        "description": desc,
        "modules": modules,
        "overall_progress_percentage": overall_progress
    }

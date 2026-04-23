from review_engine.query.languages.bash import PLUGIN as BASH_PLUGIN
from review_engine.query.languages.c import PLUGIN as C_PLUGIN
from review_engine.query.languages.cpp import PLUGIN as CPP_PLUGIN
from review_engine.query.languages.cuda import PLUGIN as CUDA_PLUGIN
from review_engine.query.languages.dockerfile import PLUGIN as DOCKERFILE_PLUGIN
from review_engine.query.languages.go import PLUGIN as GO_PLUGIN
from review_engine.query.languages.java import PLUGIN as JAVA_PLUGIN
from review_engine.query.languages.javascript import PLUGIN as JAVASCRIPT_PLUGIN
from review_engine.query.languages.python import PLUGIN as PYTHON_PLUGIN
from review_engine.query.languages.rust import PLUGIN as RUST_PLUGIN
from review_engine.query.languages.shared import PLUGIN as SHARED_PLUGIN
from review_engine.query.languages.sql import PLUGIN as SQL_PLUGIN
from review_engine.query.languages.typescript import PLUGIN as TYPESCRIPT_PLUGIN
from review_engine.query.languages.yaml import PLUGIN as YAML_PLUGIN

BUILTIN_QUERY_PLUGINS = {
    plugin.plugin_id: plugin
    for plugin in (
        SHARED_PLUGIN,
        CPP_PLUGIN,
        C_PLUGIN,
        CUDA_PLUGIN,
        PYTHON_PLUGIN,
        TYPESCRIPT_PLUGIN,
        JAVASCRIPT_PLUGIN,
        JAVA_PLUGIN,
        GO_PLUGIN,
        RUST_PLUGIN,
        BASH_PLUGIN,
        SQL_PLUGIN,
        YAML_PLUGIN,
        DOCKERFILE_PLUGIN,
    )
}

__all__ = ["BUILTIN_QUERY_PLUGINS"]

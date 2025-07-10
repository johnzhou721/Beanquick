import logging
import yaml

from .helpers import BeanquickConfigError

logger = logging.getLogger(__name__)

def load_config(config_path="config.yaml"):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        config.setdefault("defaults", {})
        config.setdefault("aliases", {})
        config.setdefault("command_templates", {})
        return config
    except FileNotFoundError:
        logger.warning(f"Config file {config_path} not found. Using empty config.")
        return {"defaults": {}, "aliases": {}, "command_templates": {}}
    except yaml.YAMLError as e:
        logger.error(f"Error parsing config file {config_path}: {e}")
        raise BeanquickConfigError(f"Error parsing config file {config_path}: {e}")

def save_config(config: dict, config_path="config.yaml"):
    """
    Save configuration dictionary to a YAML file.
    
    Args:
        config: Configuration dictionary to save
        config_path: Path to the config file (default: "config.yaml")
    
    Raises:
        BeanquickConfigError: If there's an error writing the config file
    """
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except (IOError, OSError) as e:
        raise BeanquickConfigError(f"Error writing config file {config_path}: {e}")
    except yaml.YAMLError as e:
        raise BeanquickConfigError(f"Error serializing config to YAML: {e}")
    


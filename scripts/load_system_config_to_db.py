"""
Load system configuration into the database.
This script populates the system_config table with application settings.
"""
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import text
from streamlit_app.db import engine, SessionLocal, SystemConfig


# ---------------------------------------------------------------------
# System Config Manager
# ---------------------------------------------------------------------
class SystemConfigManager:
    """
    Manages system configuration in the database.
    """
    
    def __init__(self):
        self.loaded = 0
        self.errors = []
        self._ensure_table_exists()
    
    def _ensure_table_exists(self) -> None:
        """Ensure the system_config table exists."""
        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS system_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config_key TEXT UNIQUE NOT NULL,
                        config_value TEXT,
                        description TEXT,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                print("✅ system_config table verified/created")
        except Exception as e:
            print(f"⚠️ Error creating system_config table: {e}")
    
    def get_default_configs(self) -> List[Dict[str, Any]]:
        """
        Get default system configuration values.
        
        Returns:
            List of configuration dictionaries
        """
        return [
            {
                'config_key': 'app_name',
                'config_value': 'AI Governance Platform',
                'description': 'Application name'
            },
            {
                'config_key': 'app_version',
                'config_value': '1.0.0',
                'description': 'Application version'
            },
            {
                'config_key': 'environment',
                'config_value': 'production',
                'description': 'Application environment (development, staging, production)'
            },
            {
                'config_key': 'debug_mode',
                'config_value': 'false',
                'description': 'Enable debug mode'
            },
            {
                'config_key': 'default_model',
                'config_value': 'gemini-3.6-flash',
                'description': 'Default LLM model'
            },
            {
                'config_key': 'mock_mode',
                'config_value': 'false',
                'description': 'Enable mock mode for testing'
            },
            {
                'config_key': 'audit_enabled',
                'config_value': 'true',
                'description': 'Enable audit logging'
            },
            {
                'config_key': 'max_context_tokens',
                'config_value': '4000',
                'description': 'Maximum tokens for LLM context'
            },
            {
                'config_key': 'context_history_limit',
                'config_value': '5',
                'description': 'Number of history items to include in context'
            },
            {
                'config_key': 'context_days_limit',
                'config_value': '7',
                'description': 'Days of history to include in context'
            },
            {
                'config_key': 'request_timeout_seconds',
                'config_value': '30',
                'description': 'LLM request timeout in seconds'
            },
            {
                'config_key': 'api_rate_limit',
                'config_value': '100',
                'description': 'API rate limit per minute'
            },
            {
                'config_key': 'database_url',
                'config_value': 'sqlite:///db/governance.db',
                'description': 'Database connection URL'
            },
            {
                'config_key': 'maintenance_mode',
                'config_value': 'false',
                'description': 'Enable maintenance mode'
            },
            {
                'config_key': 'last_updated',
                'config_value': datetime.now().isoformat(),
                'description': 'Last configuration update timestamp'
            }
        ]
    
    def load_defaults(self, force: bool = False) -> int:
        """
        Load default configuration values.
        
        Args:
            force: Force reload even if configs exist
        
        Returns:
            Number of configurations loaded
        """
        loaded = 0
        
        try:
            db = SessionLocal()
            configs = self.get_default_configs()
            
            for config in configs:
                key = config['config_key']
                value = config['config_value']
                description = config['description']
                
                # Check if config already exists
                existing = db.query(SystemConfig).filter(
                    SystemConfig.config_key == key
                ).first()
                
                if existing and not force:
                    continue
                
                if existing:
                    # Update existing
                    existing.config_value = value
                    existing.description = description
                    existing.updated_at = datetime.now()
                else:
                    # Create new
                    new_config = SystemConfig(
                        config_key=key,
                        config_value=value,
                        description=description,
                        updated_at=datetime.now()
                    )
                    db.add(new_config)
                
                loaded += 1
            
            db.commit()
            db.close()
            
            self.loaded = loaded
            print(f"✅ Loaded {loaded} configuration values")
            return loaded
            
        except Exception as e:
            self.errors.append(f"Error loading defaults: {e}")
            return 0
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key.
        
        Args:
            key: Configuration key
            default: Default value if key not found
        
        Returns:
            Configuration value or default
        """
        try:
            db = SessionLocal()
            config = db.query(SystemConfig).filter(
                SystemConfig.config_key == key
            ).first()
            db.close()
            
            if config:
                return config.config_value
            return default
        except Exception as e:
            print(f"⚠️ Error getting config '{key}': {e}")
            return default
    
    def set_config(self, key: str, value: str, description: str = None) -> bool:
        """
        Set a configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
            description: Optional description
        
        Returns:
            bool: True if successful
        """
        try:
            db = SessionLocal()
            
            existing = db.query(SystemConfig).filter(
                SystemConfig.config_key == key
            ).first()
            
            if existing:
                existing.config_value = value
                if description:
                    existing.description = description
                existing.updated_at = datetime.now()
            else:
                new_config = SystemConfig(
                    config_key=key,
                    config_value=value,
                    description=description or '',
                    updated_at=datetime.now()
                )
                db.add(new_config)
            
            db.commit()
            db.close()
            return True
        except Exception as e:
            print(f"❌ Error setting config '{key}': {e}")
            return False
    
    def get_all_configs(self) -> Dict[str, str]:
        """
        Get all configuration values.
        
        Returns:
            Dictionary of all configuration key-value pairs
        """
        try:
            db = SessionLocal()
            configs = db.query(SystemConfig).all()
            db.close()
            
            return {
                config.config_key: config.config_value
                for config in configs
            }
        except Exception as e:
            print(f"⚠️ Error getting all configs: {e}")
            return {}
    
    def get_configs_with_metadata(self) -> List[Dict[str, Any]]:
        """
        Get all configurations with metadata.
        
        Returns:
            List of configuration dictionaries
        """
        try:
            db = SessionLocal()
            configs = db.query(SystemConfig).all()
            db.close()
            
            return [
                {
                    'id': config.id,
                    'config_key': config.config_key,
                    'config_value': config.config_value,
                    'description': config.description,
                    'updated_at': config.updated_at.isoformat() if config.updated_at else None
                }
                for config in configs
            ]
        except Exception as e:
            print(f"⚠️ Error getting configs with metadata: {e}")
            return []
    
    def delete_config(self, key: str) -> bool:
        """
        Delete a configuration.
        
        Args:
            key: Configuration key
        
        Returns:
            bool: True if successful
        """
        try:
            db = SessionLocal()
            deleted = db.query(SystemConfig).filter(
                SystemConfig.config_key == key
            ).delete()
            db.commit()
            db.close()
            return deleted > 0
        except Exception as e:
            print(f"❌ Error deleting config '{key}': {e}")
            return False
    
    def load_all(self, force: bool = False) -> Dict[str, Any]:
        """
        Load all default configurations.
        
        Args:
            force: Force reload even if configs exist
        
        Returns:
            Dict with results
        """
        results = {
            'loaded': 0,
            'errors': []
        }
        
        print("📂 Loading system configuration...")
        print("=" * 60)
        
        # Check if configs already exist
        if not force:
            existing = self.get_all_configs()
            if existing:
                print(f"ℹ️ Database already has {len(existing)} configurations. Use --force to reload.")
                results['loaded'] = len(existing)
                return results
        
        # Load defaults
        loaded = self.load_defaults(force=force)
        results['loaded'] = loaded
        results['errors'] = self.errors
        
        print("\n" + "=" * 60)
        print(f"✅ Loaded {loaded} configuration values")
        
        if self.errors:
            print(f"\n⚠️ Errors: {len(self.errors)}")
            for err in self.errors:
                print(f"   - {err}")
        
        return results
    
    def verify_database(self) -> Dict[str, Any]:
        """
        Verify system configuration in the database.
        
        Returns:
            Dict with verification results
        """
        try:
            configs = self.get_configs_with_metadata()
            
            # Group by category (based on key prefix)
            categories = {}
            for config in configs:
                key = config['config_key']
                prefix = key.split('_')[0] if '_' in key else 'general'
                if prefix not in categories:
                    categories[prefix] = []
                categories[prefix].append(config['config_key'])
            
            return {
                'total': len(configs),
                'configs': configs,
                'categories': categories
            }
        except Exception as e:
            return {'error': str(e)}
    
    def export_to_json(self) -> Dict[str, str]:
        """
        Export all configurations to JSON.
        
        Returns:
            Dictionary of configurations
        """
        return self.get_all_configs()


# ---------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------
def get_config(key: str, default: Any = None) -> Any:
    """Get a configuration value."""
    manager = SystemConfigManager()
    return manager.get_config(key, default)


def set_config(key: str, value: str, description: str = None) -> bool:
    """Set a configuration value."""
    manager = SystemConfigManager()
    return manager.set_config(key, value, description)


def get_all_configs() -> Dict[str, str]:
    """Get all configuration values."""
    manager = SystemConfigManager()
    return manager.get_all_configs()


# ---------------------------------------------------------------------
# CLI Utility
# ---------------------------------------------------------------------
if __name__ == '__main__':
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Load system configuration into database')
    parser.add_argument('--load', action='store_true', help='Load default configurations')
    parser.add_argument('--force', action='store_true', help='Force reload')
    parser.add_argument('--verify', action='store_true', help='Verify database')
    parser.add_argument('--clear', action='store_true', help='Clear all configurations')
    parser.add_argument('--get', help='Get a configuration value by key')
    parser.add_argument('--set', help='Set a configuration value (key=value)')
    parser.add_argument('--export', action='store_true', help='Export all configurations to JSON')
    
    args = parser.parse_args()
    
    print('=' * 60)
    print('SYSTEM CONFIG LOADER')
    print('=' * 60)
    
    manager = SystemConfigManager()
    
    if args.clear:
        print('\n🗑️ Clearing system configurations...')
        try:
            db = SessionLocal()
            count = db.query(SystemConfig).delete()
            db.commit()
            db.close()
            print(f'✅ Cleared {count} configurations from database')
        except Exception as e:
            print(f'❌ Error clearing configurations: {e}')
    
    elif args.export:
        print('\n📤 Exporting configurations...')
        configs = manager.export_to_json()
        print(json.dumps(configs, indent=2, ensure_ascii=False))
        
        # Also save to file
        export_file = ROOT_DIR / 'metadata' / 'system_config_export.json'
        export_file.parent.mkdir(parents=True, exist_ok=True)
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(configs, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Exported to: {export_file}")
    
    elif args.get:
        print(f'\n🔍 Config value for: {args.get}')
        print('-' * 60)
        value = manager.get_config(args.get)
        if value is not None:
            print(f"Value: {value}")
        else:
            print("❌ Configuration key not found")
    
    elif args.set:
        print(f'\n✏️ Setting configuration: {args.set}')
        print('-' * 60)
        if '=' not in args.set:
            print("❌ Invalid format. Use: key=value")
        else:
            key, value = args.set.split('=', 1)
            if manager.set_config(key.strip(), value.strip()):
                print(f"✅ Set {key.strip()} = {value.strip()}")
            else:
                print("❌ Failed to set configuration")
    
    elif args.verify:
        print('\n📊 Verification:')
        print('-' * 60)
        result = manager.verify_database()
        if 'error' in result:
            print(f'❌ Error: {result["error"]}')
        else:
            print(f"Total Configurations: {result.get('total', 0)}")
            
            print("\n📋 Categories:")
            for category, keys in result.get('categories', {}).items():
                print(f"  - {category}: {len(keys)} keys")
            
            print("\n📋 Configurations:")
            for config in result.get('configs', []):
                print(f"  - {config['config_key']} = {config['config_value']}")
                if config['description']:
                    print(f"    Description: {config['description']}")
    
    elif args.load:
        manager.load_all(force=args.force)
    
    else:
        print("\n💡 Available commands:")
        print("  --load        Load default configurations into database")
        print("  --force       Force reload even if data exists")
        print("  --verify      Verify configurations in database")
        print("  --clear       Clear all configurations from database")
        print("  --get KEY     Get a configuration value by key")
        print("  --set K=V     Set a configuration value (e.g., --set debug_mode=true)")
        print("  --export      Export all configurations to JSON")
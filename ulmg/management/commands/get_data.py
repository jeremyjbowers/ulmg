import os
import subprocess
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = 'Download database dump from remote PostgreSQL server using pg_dump'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            default='data/sql',
            help='Directory to save the SQL dump file (default: data/sql)'
        )
        parser.add_argument(
            '--filename',
            help='Custom filename for the dump (default: uses database name)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show the pg_dump command that would be executed without running it'
        )

    def handle(self, *args, **options):
        # Required environment variables for database connection
        required_env_vars = {
            'PROD_PGDBNAME': 'Database name',
            'PROD_PGPASS': 'Database password', 
            'PROD_PGUSER': 'Database user',
            'PROD_PGHOST': 'Database host',
            'PROD_PGPORT': 'Database port'
        }

        # Check for missing environment variables
        missing_env_vars = []
        db_config = {}
        
        for env_var, description in required_env_vars.items():
            value = os.environ.get(env_var)
            if not value:
                missing_env_vars.append(f"{env_var} ({description})")
            else:
                db_config[env_var] = value

        if missing_env_vars:
            error_msg = "Missing required environment variables:\n" + "\n".join(f"  - {var}" for var in missing_env_vars)
            raise CommandError(error_msg)

        # Set up file paths
        output_dir = options['output_dir']
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            self.stdout.write(f"Created output directory: {output_dir}")

        # Determine output filename
        if options['filename']:
            filename = options['filename']
            if not filename.endswith('.sql'):
                filename += '.sql'
        else:
            filename = f"{db_config['PROD_PGDBNAME']}.sql"
        
        output_path = os.path.join(output_dir, filename)

        # Build pg_dump command
        cmd = [
            'pg_dump',
            '-U', db_config['PROD_PGUSER'],
            '-h', db_config['PROD_PGHOST'], 
            '-p', db_config['PROD_PGPORT'],
            db_config['PROD_PGDBNAME']
        ]

        # Set up environment for the subprocess
        env = os.environ.copy()
        env['PGSSLMODE'] = 'require'
        env['PGPASSWORD'] = db_config['PROD_PGPASS']

        # Show command that will be executed
        cmd_display = f"PGSSLMODE=require PGPASSWORD=*** {' '.join(cmd)} > {output_path}"
        self.stdout.write(f"Executing: {cmd_display}")

        if options['dry_run']:
            self.stdout.write(self.style.WARNING("DRY RUN - Command not executed"))
            return

        try:
            # Execute pg_dump and redirect output to file
            with open(output_path, 'w') as output_file:
                result = subprocess.run(
                    cmd,
                    stdout=output_file,
                    stderr=subprocess.PIPE,
                    env=env,
                    text=True,
                    check=True
                )

            # Check if file was created and has content
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                file_size = os.path.getsize(output_path)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully downloaded database dump to {output_path} ({file_size:,} bytes)"
                    )
                )
            else:
                raise CommandError("Dump file was not created or is empty")

        except subprocess.CalledProcessError as e:
            error_msg = f"pg_dump failed with return code {e.returncode}"
            if e.stderr:
                error_msg += f"\nError output: {e.stderr}"
            raise CommandError(error_msg)
        
        except FileNotFoundError:
            raise CommandError(
                "pg_dump command not found. Please ensure PostgreSQL client tools are installed."
            )
        
        except Exception as e:
            raise CommandError(f"Unexpected error: {str(e)}") 
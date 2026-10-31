# Kobros Backend — Migraciones con Alembic

## Flujo para agregar cambios al esquema

1. Modifica el modelo SQLAlchemy en `app/infrastructure/models/`
2. Genera la migración:
   ```bash
   docker compose exec api alembic revision --autogenerate -m "descripcion_del_cambio"
   ```
3. **Revisa** el archivo generado en `alembic/versions/` antes de aplicarlo
4. Aplica la migración:
   ```bash
   docker compose exec api alembic upgrade head
   ```

## Comandos útiles

```bash
# Ver el estado actual
docker compose exec api alembic current

# Ver historial de migraciones
docker compose exec api alembic history

# Revertir la última migración
docker compose exec api alembic downgrade -1

# Revertir hasta una revisión específica
docker compose exec api alembic downgrade <revision_id>
```

## Cómo funciona

- Las migraciones corren automáticamente al iniciar el contenedor (`alembic upgrade head` en el `CMD` del Dockerfile)
- El driver para migraciones es `psycopg2` (síncrono), aunque la app usa `asyncpg`
- La URL se lee de la variable de entorno `DATABASE_URL`, sustituyendo `postgresql+asyncpg://` por `postgresql+psycopg2://`

## Contexto histórico

- La migración `baseline_schema` (rev `8721fdd594fe`) es el punto de partida — no crea tablas, solo marca el estado inicial
- Las tablas se creaban antes con `Base.metadata.create_all()` en el lifespan de la app; ya no se usa ese mecanismo

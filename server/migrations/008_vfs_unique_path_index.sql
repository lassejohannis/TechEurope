-- Enforce VFS path uniqueness inside an entity type.
-- Req: unique index on (entity_type, attrs->>'vfs_path')

create unique index if not exists entities_type_vfs_path_unique
  on entities (entity_type, (attrs->>'vfs_path'))
  where attrs ? 'vfs_path';

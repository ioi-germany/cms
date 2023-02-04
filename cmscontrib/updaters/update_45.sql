begin;

alter table contests add restricted_time varchar;

rollback; -- change this to: commit;

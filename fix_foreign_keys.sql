-- 외래키 제약 조건 수정: project_members 테이블에서 CASCADE 설정
-- 현재 NO ACTION으로 되어 있어서 프로젝트 삭제 시 오류 발생

BEGIN;

-- 1. 기존 외래키 제약 조건 삭제
ALTER TABLE IF EXISTS public.project_members 
DROP CONSTRAINT IF EXISTS project_member_pro_id;

-- 2. CASCADE 옵션으로 새로운 외래키 제약 조건 추가
ALTER TABLE IF EXISTS public.project_members
ADD CONSTRAINT project_member_pro_id FOREIGN KEY (project_id)
REFERENCES public.projects (project_id) MATCH SIMPLE
ON UPDATE NO ACTION
ON DELETE CASCADE;

-- 3. project_invitations 테이블도 CASCADE로 수정
ALTER TABLE IF EXISTS public.project_invitations
DROP CONSTRAINT IF EXISTS project_invitations_project_id_fkey;

ALTER TABLE IF EXISTS public.project_invitations
ADD CONSTRAINT project_invitations_project_id_fkey FOREIGN KEY (project_id)
REFERENCES public.projects (project_id) MATCH SIMPLE
ON UPDATE NO ACTION
ON DELETE CASCADE;

-- 인덱스 재생성 (삭제되었을 수 있으므로)
CREATE INDEX IF NOT EXISTS project_users_project_id_idx
ON public.project_members(project_id);

COMMIT;

-- 검증 쿼리 (실행하여 CASCADE 설정이 적용되었는지 확인)
-- SELECT 
--     tc.constraint_name, 
--     tc.table_name, 
--     kcu.column_name,
--     ccu.table_name AS foreign_table_name,
--     ccu.column_name AS foreign_column_name,
--     rc.delete_rule
-- FROM 
--     information_schema.table_constraints AS tc 
--     JOIN information_schema.key_column_usage AS kcu 
--       ON tc.constraint_name = kcu.constraint_name
--     JOIN information_schema.constraint_column_usage AS ccu 
--       ON ccu.constraint_name = tc.constraint_name
--     JOIN information_schema.referential_constraints AS rc 
--       ON tc.constraint_name = rc.constraint_name
-- WHERE tc.constraint_type = 'FOREIGN KEY' 
--   AND (tc.table_name = 'project_members' OR tc.table_name = 'project_invitations')
--   AND ccu.table_name = 'projects';
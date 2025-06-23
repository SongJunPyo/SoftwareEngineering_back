-- ===================================================================
-- 업무 상태값 통일 마이그레이션 스크립트
-- 목적: 'In progress' → 'in_progress'로 통일하여 상태 관리 일관성 확보
-- ===================================================================

-- 1. 현재 상태값 확인
SELECT 
    status,
    COUNT(*) as count
FROM tasks 
GROUP BY status 
ORDER BY status;

-- 2. 'In progress' → 'in_progress'로 변경
UPDATE tasks 
SET status = 'in_progress', 
    updated_at = NOW()
WHERE status = 'In progress';

-- 3. 변경 결과 확인
SELECT 
    status,
    COUNT(*) as count
FROM tasks 
GROUP BY status 
ORDER BY status;

-- 4. updated_at 자동 갱신을 위한 트리거 설정 (기존 코드 유지)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 트리거 생성 (이미 존재하면 먼저 삭제)
DROP TRIGGER IF EXISTS update_tasks_updated_at ON public.tasks;
CREATE TRIGGER update_tasks_updated_at
    BEFORE UPDATE ON public.tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 5. 마이그레이션 완료 후 최종 확인
SELECT 
    'Migration completed!' as message,
    COUNT(*) as total_tasks,
    COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress_count,
    COUNT(CASE WHEN status = 'In progress' THEN 1 END) as old_format_count
FROM tasks;
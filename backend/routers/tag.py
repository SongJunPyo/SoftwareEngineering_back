from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.database.base import get_db
from backend.middleware.auth import verify_token
from backend.models.tag import Tag
from backend.models.tag import TaskTag
from backend.models.project import Project, ProjectMember
from backend.models.task import Task as TaskModel
from backend.schemas.Tag import TagCreateRequest, TagUpdateRequest, TagResponse
from backend.utils.activity_logger import log_tag_activity

router = APIRouter(prefix="/api/v1/projects/{project_id}/tags", tags=["tags"])

@router.get("/", response_model=List[TagResponse])
def get_project_tags(
    project_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="프로젝트 멤버만 태그를 조회할 수 있습니다.")
    
    tags = db.query(Tag).filter(Tag.project_id == project_id).all()
    return tags

@router.post("/", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
def create_project_tag(
    project_id: int,
    tag_request: TagCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    if not member or member.role == 'viewer':
        raise HTTPException(status_code=403, detail="태그를 생성할 권한이 없습니다.")
    
    existing_tag = db.query(Tag).filter(
        Tag.project_id == project_id,
        Tag.tag_name == tag_request.tag_name
    ).first()
    if existing_tag:
        raise HTTPException(status_code=400, detail="이미 존재하는 태그입니다.")
    
    tag = Tag(project_id=project_id, tag_name=tag_request.tag_name)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    
    # Activity Log 작성
    try:
        log_tag_activity(
            db=db,
            user=current_user,
            tag_name=tag_request.tag_name,
            action="create",
            project_id=project_id
        )
        db.commit()
    except Exception as e:
        print(f"태그 생성 로그 작성 실패: {e}")
    
    return tag

@router.put("/{tag_name}", response_model=TagResponse)
def update_project_tag(
    project_id: int,
    tag_name: str,
    tag_update: TagUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    if not member or member.role == 'viewer':
        raise HTTPException(status_code=403, detail="태그를 수정할 권한이 없습니다.")
        
    tag = db.query(Tag).filter(Tag.tag_name == tag_name, Tag.project_id == project_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="태그를 찾을 수 없습니다.")
    
    if tag.tag_name != tag_update.tag_name:
        existing_tag = db.query(Tag).filter(
            Tag.project_id == project_id,
            Tag.tag_name == tag_update.tag_name
        ).first()
        if existing_tag:
            raise HTTPException(status_code=400, detail="이미 존재하는 태그명입니다.")
    
    # TaskTag 테이블의 tag_name도 함께 업데이트
    db.query(TaskTag).filter(
        TaskTag.task_id.in_(db.query(TaskModel.task_id).filter(TaskModel.project_id == project_id)),
        TaskTag.tag_name == tag_name
    ).update({"tag_name": tag_update.tag_name}, synchronize_session=False)

    tag.tag_name = tag_update.tag_name
    db.commit()
    db.refresh(tag)
    return tag

@router.delete("/{tag_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_tag(
    project_id: int,
    tag_name: str,
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    if not member or member.role == 'viewer':
        raise HTTPException(status_code=403, detail="태그를 삭제할 권한이 없습니다.")

    tag = db.query(Tag).filter(Tag.tag_name == tag_name, Tag.project_id == project_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="태그를 찾을 수 없습니다.")
    
    # Activity Log 작성 (삭제 전에)
    try:
        log_tag_activity(
            db=db,
            user=current_user,
            tag_name=tag_name,
            action="delete",
            project_id=project_id
        )
        db.commit()
    except Exception as e:
        print(f"태그 삭제 로그 작성 실패: {e}")
    
    # TaskTag 테이블에서 연관된 항목 먼저 삭제
    db.query(TaskTag).filter(
        TaskTag.tag_name == tag_name,
        TaskTag.task_id.in_(db.query(TaskModel.task_id).filter(TaskModel.project_id == project_id))
    ).delete(synchronize_session=False)

    db.delete(tag)
    db.commit()
    return None

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.database.base import get_db
from backend.middleware.auth import verify_token
from backend.models.tag import Tag, TaskTag
from backend.models.project import Project, ProjectMember
from backend.models.task import Task as TaskModel
from backend.schemas.Tag import TagCreateRequest, TagUpdateRequest, TagResponse, TaskTagCreateRequest, TaskTagResponse

router = APIRouter(prefix="/api/v1")

# 프로젝트별 태그 목록 조회
@router.get("/projects/{project_id}/tags", response_model=List[TagResponse])
def get_project_tags(
    project_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    # 프로젝트 존재 여부 확인
    project = db.query(Project).filter_by(project_id=project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프로젝트를 찾을 수 없습니다."
        )
    
    # 사용자가 프로젝트 멤버인지 확인
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 프로젝트의 멤버만 태그를 조회할 수 있습니다."
        )
    
    tags = db.query(Tag).filter_by(project_id=project_id).all()
    return tags

# 프로젝트에 태그 생성
@router.post("/projects/{project_id}/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
def create_project_tag(
    project_id: int,
    tag_request: TagCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    # 프로젝트 존재 여부 확인
    project = db.query(Project).filter_by(project_id=project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프로젝트를 찾을 수 없습니다."
        )
    
    # 사용자가 프로젝트 멤버인지 확인
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 프로젝트의 멤버만 태그를 생성할 수 있습니다."
        )
    
    # 중복 태그 확인
    existing_tag = db.query(Tag).filter(
        Tag.project_id == project_id,
        Tag.tag_name == tag_request.tag_name
    ).first()
    if existing_tag:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 존재하는 태그입니다."
        )
    
    # 태그 생성
    tag = Tag(
        project_id=project_id,
        tag_name=tag_request.tag_name
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    
    return tag

# 태그 수정
@router.put("/projects/{project_id}/tags/{old_tag_name}", response_model=TagResponse)
def update_project_tag(
    project_id: int,
    old_tag_name: str,
    tag_update: TagUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    # 프로젝트 존재 여부 확인
    project = db.query(Project).filter_by(project_id=project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프로젝트를 찾을 수 없습니다."
        )
    
    # 사용자가 프로젝트 멤버인지 확인
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 프로젝트의 멤버만 태그를 수정할 수 있습니다."
        )
    
    # 기존 태그 확인
    tag = db.query(Tag).filter(
        Tag.project_id == project_id,
        Tag.tag_name == old_tag_name
    ).first()
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="태그를 찾을 수 없습니다."
        )
    
    # 새 태그명이 이미 존재하는지 확인
    if old_tag_name != tag_update.tag_name:
        existing_tag = db.query(Tag).filter(
            Tag.project_id == project_id,
            Tag.tag_name == tag_update.tag_name
        ).first()
        if existing_tag:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 존재하는 태그명입니다."
            )
    
    # task_tags 테이블의 태그명도 업데이트
    if old_tag_name != tag_update.tag_name:
        # 이 프로젝트의 모든 작업에서 해당 태그명 업데이트
        task_tags = db.query(TaskTag).join(TaskModel).filter(
            TaskModel.project_id == project_id,
            TaskTag.tag_name == old_tag_name
        ).all()
        
        for task_tag in task_tags:
            task_tag.tag_name = tag_update.tag_name
    
    # 태그 수정
    tag.tag_name = tag_update.tag_name
    db.commit()
    db.refresh(tag)
    
    return tag

# 태그 삭제
@router.delete("/projects/{project_id}/tags/{tag_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_tag(
    project_id: int,
    tag_name: str,
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    # 프로젝트 존재 여부 확인
    project = db.query(Project).filter_by(project_id=project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프로젝트를 찾을 수 없습니다."
        )
    
    # 사용자가 프로젝트 멤버인지 확인
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 프로젝트의 멤버만 태그를 삭제할 수 있습니다."
        )
    
    # 태그 확인
    tag = db.query(Tag).filter(
        Tag.project_id == project_id,
        Tag.tag_name == tag_name
    ).first()
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="태그를 찾을 수 없습니다."
        )
    
    # 연관된 task_tags 먼저 삭제
    task_tags = db.query(TaskTag).join(TaskModel).filter(
        TaskModel.project_id == project_id,
        TaskTag.tag_name == tag_name
    ).all()
    
    for task_tag in task_tags:
        db.delete(task_tag)
    
    # 태그 삭제
    db.delete(tag)
    db.commit()
    
    return None

# 특정 작업의 태그 목록 조회
@router.get("/tasks/{task_id}/tags", response_model=List[TaskTagResponse])
def get_task_tags(
    task_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    # 작업 존재 여부 확인
    task = db.query(TaskModel).filter_by(task_id=task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="작업을 찾을 수 없습니다."
        )
    
    # 사용자가 프로젝트 멤버인지 확인
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == task.project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 프로젝트의 멤버만 작업 태그를 조회할 수 있습니다."
        )
    
    task_tags = db.query(TaskTag).filter_by(task_id=task_id).all()
    return task_tags

# 작업에 태그 할당/업데이트
@router.post("/tasks/{task_id}/tags", response_model=List[TaskTagResponse])
def update_task_tags(
    task_id: int,
    tag_request: TaskTagCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    # 작업 존재 여부 확인
    task = db.query(TaskModel).filter_by(task_id=task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="작업을 찾을 수 없습니다."
        )
    
    # 사용자가 프로젝트 멤버인지 확인
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == task.project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 프로젝트의 멤버만 작업 태그를 수정할 수 있습니다."
        )
    
    # 태그들이 해당 프로젝트에 존재하는지 확인
    for tag_name in tag_request.tag_names:
        existing_tag = db.query(Tag).filter(
            Tag.project_id == task.project_id,
            Tag.tag_name == tag_name
        ).first()
        if not existing_tag:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"태그 '{tag_name}'이 해당 프로젝트에 존재하지 않습니다."
            )
    
    # 기존 작업 태그 모두 삭제
    db.query(TaskTag).filter_by(task_id=task_id).delete()
    
    # 새 태그들 추가
    new_task_tags = []
    for tag_name in tag_request.tag_names:
        task_tag = TaskTag(task_id=task_id, tag_name=tag_name)
        db.add(task_tag)
        new_task_tags.append(task_tag)
    
    db.commit()
    
    # 생성된 태그들 반환
    return new_task_tags

# 작업에서 특정 태그 제거
@router.delete("/tasks/{task_id}/tags/{tag_name}", status_code=status.HTTP_204_NO_CONTENT)
def remove_task_tag(
    task_id: int,
    tag_name: str,
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    # 작업 존재 여부 확인
    task = db.query(TaskModel).filter_by(task_id=task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="작업을 찾을 수 없습니다."
        )
    
    # 사용자가 프로젝트 멤버인지 확인
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == task.project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 프로젝트의 멤버만 작업 태그를 제거할 수 있습니다."
        )
    
    # 작업 태그 확인 및 삭제
    task_tag = db.query(TaskTag).filter(
        TaskTag.task_id == task_id,
        TaskTag.tag_name == tag_name
    ).first()
    if not task_tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 작업에 지정된 태그를 찾을 수 없습니다."
        )
    
    db.delete(task_tag)
    db.commit()
    
    return None
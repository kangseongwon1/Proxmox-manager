/**
 * 백업 관리 JavaScript
 */

console.log('[backups.js] 백업 관리 페이지 로드됨');

// 알림 시스템은 navigation.js에서 중앙 관리됨

// 초기 알림 로드는 navigation.js에서 중앙 관리됨

// 전역 변수 (중복 선언 방지)
if (typeof window.backupData === 'undefined') {
    window.backupData = [];
}

// 페이지 로드 시 실행
$(document).ready(function() {
    console.log('[backups.js] 페이지 초기화 시작');
    
    // 초기 통계값 설정
    $('#backup-count').text('0개');
    $('#total-size').text('0 GB');
    
    // 새로고침 버튼 이벤트
    $('#refresh-backups').on('click', function() {
        console.log('[backups.js] 새로고침 버튼 클릭');
        loadBackupData();
    });
    
    // 테스트 알림 버튼 이벤트
    $('#test-notification').on('click', function() {
        console.log('[backups.js] 테스트 알림 버튼 클릭');
        testNotification();
    });
    
    // 알림 시스템은 navigation.js에서 자동 초기화됨
    loadBackupData();
});

/**
 * 테스트 알림 생성
 */
function testNotification() {
    console.log('[backups.js] 테스트 알림 생성 시작');
    
    $.ajax({
        url: '/api/test/notification',
        method: 'POST',
        contentType: 'application/json',
        success: function(response) {
            console.log('[backups.js] 테스트 알림 생성 성공:', response);
            alert('테스트 알림이 생성되었습니다. notification 드롭다운을 확인하세요.');
        },
        error: function(xhr, status, error) {
            console.error('[backups.js] 테스트 알림 생성 실패:', xhr, status, error);
            alert('테스트 알림 생성에 실패했습니다: ' + (xhr.responseJSON?.error || error));
        }
    });
}

/**
 * 백업 데이터 로드
 */
function loadBackupData() {
    console.log('[backups.js] 백업 데이터 로드 시작');
    
    $('#backups-tbody').html('<tr><td colspan="6" class="text-center"><i class="fas fa-spinner fa-spin"></i> 백업 목록을 불러오는 중...</td></tr>');
    
    $.ajax({
        url: '/api/backups/nodes',
        method: 'GET',
        timeout: 30000,
        success: function(response) {
            console.log('[backups.js] API 응답:', response);
            
            if (response.success && response.data) {
                const rawBackups = response.data.backups || [];
                console.log('[backups.js] 백업 데이터:', rawBackups);
                
                // VM별로 그룹화
                window.backupData = groupBackupsByVM(rawBackups);
                console.log('[backups.js] 그룹화된 데이터:', window.backupData);
                
                // 백업 통계 업데이트
                updateBackupStats();
                
                renderBackupTable();
            } else {
                $('#backups-tbody').html('<tr><td colspan="6" class="text-center text-danger">백업 목록을 불러오는데 실패했습니다.</td></tr>');
            }
        },
        error: function(xhr, status, error) {
            console.error('[backups.js] API 호출 실패:', xhr, status, error);
            $('#backups-tbody').html('<tr><td colspan="6" class="text-center text-danger">백업 목록을 불러오는데 실패했습니다.</td></tr>');
        }
    });
}

/**
 * VM별로 백업 그룹화
 */
function groupBackupsByVM(rawBackups) {
    console.log('[backups.js] 그룹화 시작, 원본 데이터:', rawBackups);
    
    const vmGroups = {};
    
    rawBackups.forEach((backup, index) => {
        console.log(`[backups.js] 백업 ${index}:`, backup);
        
        const vmKey = `${backup.vm_name || backup.vm_id}`;
        console.log(`[backups.js] VM 키: ${vmKey}`);
        
        if (!vmGroups[vmKey]) {
            vmGroups[vmKey] = {
                vm_name: backup.vm_name || `VM-${backup.vm_id}`,
                vm_id: backup.vm_id,
                node: backup.node,
                backups: [],
                latest_backup: null,
                total_size_gb: 0
            };
            console.log(`[backups.js] 새 VM 그룹 생성:`, vmGroups[vmKey]);
        }
        
        vmGroups[vmKey].backups.push(backup);
        vmGroups[vmKey].total_size_gb += backup.size_gb || 0;
        
        // 최신 백업 찾기 (ctime 사용)
        if (!vmGroups[vmKey].latest_backup || 
            (backup.ctime && backup.ctime > vmGroups[vmKey].latest_backup.ctime)) {
            vmGroups[vmKey].latest_backup = backup;
        }
    });
    
    const result = Object.values(vmGroups);
    console.log('[backups.js] 그룹화 결과:', result);
    return result;
}

/**
 * 백업 테이블 렌더링
 */
function renderBackupTable() {
    const tbody = $('#backups-tbody');
    
    if (window.backupData.length === 0) {
        tbody.html('<tr><td colspan="6" class="text-center">백업이 없습니다.</td></tr>');
        return;
    }
    
    const rows = window.backupData.map((vm, index) => {
        console.log(`[backups.js] VM ${index} 렌더링:`, vm);
        
        const latestBackup = vm.latest_backup;
        console.log(`[backups.js] VM ${vm.vm_name} 최신 백업:`, latestBackup);
        
        const creationTime = latestBackup ? formatDateTime(latestBackup.ctime) : '-';
        const backupFile = latestBackup ? getBackupFileName(latestBackup.filename || latestBackup.name) : '-';
        const storage = latestBackup ? latestBackup.storage : '-';
        
        const row = `
            <tr class="backup-row" data-vm-id="${vm.vm_id}">
                <td><strong>${vm.vm_name}</strong><br><small class="text-muted">ID: ${vm.vm_id}</small></td>
                <td>${vm.node}</td>
                <td><code>${backupFile}</code></td>
                <td>${storage}</td>
                <td>${creationTime}</td>
                <td>${vm.total_size_gb.toFixed(2)} GB</td>
            </tr>
        `;
        
        console.log(`[backups.js] VM ${vm.vm_name} 생성된 행:`, row);
        return row;
    }).join('');
    
    console.log('[backups.js] 전체 생성된 HTML:', rows);
    tbody.html(rows);
    
    // 행 클릭 이벤트 추가
    $('.backup-row').on('click', function() {
        const vmId = $(this).data('vm-id');
        const vmData = window.backupData.find(vm => vm.vm_id == vmId);
        if (vmData) {
            showVMBackupDetail(vmData);
        }
    });
    
    console.log('[backups.js] 테이블 렌더링 완료, 행 수:', window.backupData.length);
}

/**
 * VM 백업 상세 모달 표시
 */
function showVMBackupDetail(vmData) {
    console.log('[backups.js] VM 백업 상세 표시:', vmData);
    
    // 모달 제목 설정
    $('#vm-backup-modal-title').text(`${vmData.vm_name} (ID: ${vmData.vm_id}) 백업 목록`);
    
    // 백업 목록을 시간순으로 정렬 (최신순)
    const sortedBackups = [...vmData.backups].sort((a, b) => b.ctime - a.ctime);
    
    // 백업 상세 테이블 생성
    const tableHtml = `
        <div class="table-responsive">
            <table class="table table-hover">
                <thead class="table-light">
                    <tr>
                        <th style="width: 30%;">백업 파일명</th>
                        <th style="width: 15%;">저장위치</th>
                        <th style="width: 20%;">생성시간</th>
                        <th style="width: 15%;">크기</th>
                        <th style="width: 20%;">작업</th>
                    </tr>
                </thead>
                <tbody id="vm-backup-detail-tbody">
                    ${sortedBackups.map(backup => `
                        <tr data-filename="${backup.filename}" data-vm-id="${vmData.vm_id}" data-node="${vmData.node}">
                            <td><code class="backup-filename">${getBackupFileName(backup.filename)}</code></td>
                            <td>${backup.storage}</td>
                            <td>${formatDateTime(backup.ctime)}</td>
                            <td>${(backup.size_gb || 0).toFixed(2)} GB</td>
                            <td>
                                <div class="btn-group btn-group-sm" role="group">
                                    <button type="button" class="btn backup-action-btn restore-btn" 
                                            onclick="restoreBackup('${vmData.node}', '${vmData.vm_id}', '${backup.filename}')">
                                        <i class="fas fa-undo"></i> 복원
                                    </button>
                                    <button type="button" class="btn backup-action-btn delete-btn" 
                                            onclick="deleteBackup('${vmData.node}', '${backup.filename}', this)">
                                        <i class="fas fa-trash"></i> 삭제
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
    
    $('#vm-backup-detail-content').html(tableHtml);
    
    // 모달 표시
    $('#vm-backup-detail-modal').modal('show');
}

/**
 * 백업 복원
 */
function restoreBackup(node, vmId, filename) {
    console.log('[backups.js] 백업 복원:', { node, vmId, filename });
    
    if (!confirm('정말로 이 백업으로 복원하시겠습니까?\\n\\n⚠️ 현재 VM의 모든 데이터가 백업 시점으로 되돌아갑니다.')) {
        return;
    }
    
    const restoreBtn = event.target.closest('.restore-btn');
    const originalContent = restoreBtn.innerHTML;
    
    // 버튼 비활성화
    restoreBtn.disabled = true;
    restoreBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 복원 중...';
    
    $.ajax({
        url: '/api/backups/restore',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            node: node,
            vm_id: vmId,
            filename: filename
        }),
        success: function(response) {
            console.log('[backups.js] 백업 복원 성공:', response);
            alert('백업 복원이 시작되었습니다.');
            
            // 모달 닫기
            $('#vm-backup-detail-modal').modal('hide');
            
            // 백업 목록 새로고침
            setTimeout(() => {
                loadBackupData();
            }, 2000);
        },
        error: function(xhr, status, error) {
            console.error('[backups.js] 백업 복원 실패:', xhr, status, error);
            let errorMessage = '백업 복원에 실패했습니다.';
            
            if (xhr.responseJSON && xhr.responseJSON.error) {
                errorMessage = xhr.responseJSON.error;
            }
            
            alert(errorMessage);
        },
        complete: function() {
            // 버튼 복원
            restoreBtn.disabled = false;
            restoreBtn.innerHTML = originalContent;
        }
    });
}

/**
 * 백업 삭제
 */
function deleteBackup(node, filename, buttonElement) {
    console.log('[backups.js] 백업 삭제:', { node, filename });
    
    if (!confirm('정말로 이 백업을 삭제하시겠습니까?\\n\\n⚠️ 삭제된 백업은 복구할 수 없습니다.')) {
        return;
    }
    
    const deleteBtn = $(buttonElement);
    const originalContent = deleteBtn.html();
    const row = deleteBtn.closest('tr');
    
    // 버튼 비활성화
    deleteBtn.prop('disabled', true);
    deleteBtn.html('<i class="fas fa-spinner fa-spin"></i> 삭제 중...');
    
    $.ajax({
        url: '/api/backups/delete',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            node: node,
            filename: filename
        }),
        success: function(response) {
            console.log('[backups.js] 백업 삭제 성공:', response);
            alert('백업이 성공적으로 삭제되었습니다.');
            
            // 테이블에서 해당 행 제거
            row.fadeOut(300, function() {
                $(this).remove();
                
                // 남은 행이 없으면 모달 닫기
                if ($('#vm-backup-detail-tbody tr').length === 0) {
                    $('#vm-backup-detail-modal').modal('hide');
                }
            });
            
            // 백업 목록 새로고침 및 통계 업데이트
            setTimeout(() => {
                loadBackupData();
            }, 1000);
        },
        error: function(xhr, status, error) {
            console.error('[backups.js] 백업 삭제 실패:', xhr, status, error);
            let errorMessage = '백업 삭제에 실패했습니다.';
            
            if (xhr.responseJSON && xhr.responseJSON.error) {
                errorMessage = xhr.responseJSON.error;
            }
            
            alert(errorMessage);
            
            // 버튼 복원
            deleteBtn.prop('disabled', false);
            deleteBtn.html(originalContent);
        }
    });
}

/**
 * 백업 통계 업데이트
 */
function updateBackupStats() {
    let totalBackupCount = 0;
    let totalSizeGB = 0;
    
    window.backupData.forEach(vm => {
        totalBackupCount += vm.backups.length;
        totalSizeGB += vm.total_size_gb;
    });
    
    console.log('[backups.js] 백업 통계:', { totalBackupCount, totalSizeGB });
    
    // 헤더 배지 업데이트
    $('#backup-count').text(`${totalBackupCount}개`);
    $('#total-size').text(`${totalSizeGB.toFixed(2)} GB`);
    
    // 상단 배지도 업데이트 (있는 경우)
    if ($('#totalBackupCount').length) {
        $('#totalBackupCount').text(totalBackupCount);
    }
    if ($('#totalBackupSize').length) {
        $('#totalBackupSize').text(`${totalSizeGB.toFixed(2)} GB`);
    }
}

/**
 * 유틸리티 함수들
 */
function formatDateTime(timestamp) {
    if (!timestamp) return '-';
    
    // Unix timestamp를 Date 객체로 변환 (초 단위를 밀리초로)
    const date = new Date(timestamp * 1000);
    return date.toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function getBackupFileName(fullName) {
    if (!fullName) return '-';
    
    // local:backup/filename 형식에서 filename만 추출
    const parts = fullName.split('/');
    return parts[parts.length - 1];
}
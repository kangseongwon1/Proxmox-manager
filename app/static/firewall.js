// Datacenter Security Group 관리 시스템
window.loadFirewallGroups = function() {
    console.log('[firewall.js] Datacenter Security Group 목록 로드 시작');
    $('#main-content').html('<div class="text-center py-5"><i class="fas fa-spinner fa-spin fa-2x"></i><br>로딩 중...</div>');
    
    $.ajax({
        url: '/api/firewall/groups',
        method: 'GET',
        dataType: 'json',
        success: function(data) {
            console.log('[firewall.js] Security Group 데이터 로드 성공:', data);
            console.log('[firewall.js] data 타입:', typeof data);
            console.log('[firewall.js] data 구조:', Object.keys(data));
            console.log('[firewall.js] groups 배열:', data.groups);
            console.log('[firewall.js] groups 타입:', typeof data.groups);
            console.log('[firewall.js] groups 길이:', data.groups ? data.groups.length : 'undefined');
            console.log('[firewall.js] groups 내용:', JSON.stringify(data.groups, null, 2));
            
            $.get('/firewall/groups/content', function(html) {
                console.log('[firewall.js] HTML 템플릿 로드 성공');
                $('#main-content').html(html);
                renderSecurityGroups(data.groups || []);
            }).fail(function(xhr) {
                console.error('[firewall.js] HTML 템플릿 로드 실패:', xhr);
                $('#main-content').html(`<div class="text-center py-5 text-danger"><i class="fas fa-exclamation-triangle fa-2x"></i><br>HTML 템플릿 로드 실패</div>`);
            });
        },
        error: function(xhr, status, error) {
            console.error('[firewall.js] Security Group 데이터 로드 실패:', xhr);
            
            // API 호출 실패 시에도 HTML 템플릿은 로드하고 테스트 데이터 표시
      $.get('/firewall/groups/content', function(html) {
                console.log('[firewall.js] HTML 템플릿 로드 성공 (API 실패 시)');
        $('#main-content').html(html);
                
                // 테스트 데이터로 표시
                const testGroups = [
                    {
                        name: 'web-servers',
                        description: '웹서버용 Security Group (테스트)',
                        instance_count: 3
                    },
                    {
                        name: 'db-servers',
                        description: '데이터베이스 서버용 Security Group (테스트)',
                        instance_count: 2
                    },
                    {
                        name: 'management',
                        description: '관리용 Security Group (테스트)',
                        instance_count: 1
                    }
                ];
                
                console.log('[firewall.js] 테스트 데이터로 렌더링:', testGroups);
                renderSecurityGroups(testGroups);
                
                // 오류 메시지 표시
                let errorMsg = 'Security Group 조회 실패';
                if (xhr.status === 501) {
                    errorMsg = 'Datacenter Security Group API가 지원되지 않습니다.';
                } else if (xhr.status === 401) {
                    errorMsg = '인증이 필요합니다. 다시 로그인해주세요.';
                } else if (xhr.status === 403) {
                    errorMsg = '권한이 없습니다.';
                } else if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMsg = xhr.responseJSON.error;
                } else if (xhr.responseText) {
                    errorMsg = `서버 오류: ${xhr.responseText}`;
                }
                
                // 오류 메시지를 테이블 위에 표시
                $('#fw-group-tbody').before(`<tr><td colspan="4" class="text-center text-warning"><i class="fas fa-exclamation-triangle"></i> ${errorMsg} (테스트 데이터 표시)</td></tr>`);
            }).fail(function(xhr) {
                console.error('[firewall.js] HTML 템플릿 로드 실패:', xhr);
                $('#main-content').html(`<div class="text-center py-5 text-danger"><i class="fas fa-exclamation-triangle fa-2x"></i><br>HTML 템플릿 로드 실패</div>`);
            });
        }
    });
}

// Security Group 목록 렌더링
function renderSecurityGroups(groups) {
    console.log('[firewall.js] Security Group 목록 렌더링 시작');
    console.log('[firewall.js] groups:', groups);
    console.log('[firewall.js] groups 타입:', typeof groups);
    console.log('[firewall.js] groups 길이:', groups ? groups.length : 'undefined');
    console.log('[firewall.js] groups 배열 여부:', Array.isArray(groups));
    
    const $tbody = $('#fw-group-tbody');
    console.log('[firewall.js] tbody 요소 찾기:', $tbody.length > 0 ? '성공' : '실패');
    
    if (!$tbody.length) {
        console.error('[firewall.js] #fw-group-tbody 요소를 찾을 수 없습니다!');
        return;
    }
    
    $tbody.empty();
    console.log('[firewall.js] tbody 비움 완료');
    
    if (!groups || !groups.length) {
        console.log('[firewall.js] 그룹이 없음, 빈 메시지 표시');
        $tbody.append('<tr><td colspan="4" class="text-center text-muted">등록된 Security Group이 없습니다.</td></tr>');
      return;
    }
    
    console.log('[firewall.js] 그룹 렌더링 시작, 개수:', groups.length);
    groups.forEach((group, index) => {
        console.log(`[firewall.js] Security Group ${index + 1}:`, group);
        
        const rowHtml = `
            <tr>
                <td class="fw-bold">${group.name || '이름 없음'}</td>
                <td>
                    <div>${group.description || ''}</div>
                    <small class="text-muted">할당된 VM: ${group.vms ? group.vms.join(', ') : '없음'}</small>
                </td>
                <td>${group.instance_count || 0}</td>
                <td>
                    <button class="btn btn-outline-primary btn-sm sg-config-btn" data-group="${group.name}">
                        <i class="fas fa-cog"></i> 설정
                    </button>
                    <button class="btn btn-outline-danger btn-sm sg-delete-btn" data-group="${group.name}">
                        <i class="fas fa-trash"></i> 삭제
                    </button>
          </td>
        </tr>
        `;
        
        console.log(`[firewall.js] Security Group ${index + 1} HTML:`, rowHtml);
        $tbody.append(rowHtml);
        console.log(`[firewall.js] Security Group ${index + 1} 추가 완료`);
    });
    console.log('[firewall.js] 그룹 렌더링 완료');
}

// Security Group 설정 모달 열기
function openSecurityGroupConfig(groupName) {
    console.log('[firewall.js] Security Group 설정 모달 열기:', groupName);
    
    // 모달에 그룹 이름 저장
    $('#security-group-config-modal').data('group-name', groupName);
    
    // 그룹 정보 로드
    loadSecurityGroupDetail(groupName);
    
    // 모달 표시
    $('#security-group-config-modal').modal('show');
}

// Security Group 상세 정보 로드
function loadSecurityGroupDetail(groupName) {
    console.log('[firewall.js] Security Group 상세 정보 로드:', groupName);
    
    $.ajax({
        url: `/api/firewall/groups/${groupName}`,
        method: 'GET',
        dataType: 'json',
        success: function(data) {
            console.log('[firewall.js] Security Group 상세 정보 로드 성공:', data);
            
            if (data.success && data.group) {
                const group = data.group;
                
                // 그룹 정보 설정
                $('#sg-group-name').text(group.name);
                $('#sg-group-name-input').val(group.name);
                $('#sg-group-description-input').val(group.description);
                
                // 규칙 목록 렌더링
                renderSecurityGroupRules(group.rules || []);
            }
        },
        error: function(xhr) {
            console.error('[firewall.js] Security Group 상세 정보 로드 실패:', xhr);
            alert('Security Group 상세 정보 로드에 실패했습니다.');
        }
    });
}

// Security Group 규칙 렌더링
function renderSecurityGroupRules(rules) {
    console.log('[firewall.js] Security Group 규칙 렌더링:', rules);
    
    const $tbody = $('#sg-rules-tbody');
    $tbody.empty();
    
    if (!rules || !rules.length) {
        $tbody.append('<tr><td colspan="8" class="text-center text-muted">등록된 규칙이 없습니다.</td></tr>');
        return;
    }
    
    rules.forEach((rule, index) => {
        console.log(`[firewall.js] 규칙 ${index + 1}:`, rule);
        
        // 매크로 정보 표시
        const macroInfo = rule.macro ? `<br><small class="text-info"><i class="fas fa-tag"></i> ${rule.macro}</small>` : '';
        
        // 포트 정보 표시 (dport 사용)
        const portInfo = rule.dport ? rule.dport : '-';
        
        // 프로토콜 정보 표시 + 매크로 동시 표기
        const protoText = rule.proto ? rule.proto.toUpperCase() : 'ANY';
        const macroBadge = rule.macro ? ` <span class="badge bg-info text-dark">${rule.macro}</span>` : '';
        const protocolInfo = `${protoText}${macroBadge}`;
        
        // 방향 정보 표시
        const directionInfo = rule.type === 'in' ? '인바운드' : rule.type === 'out' ? '아웃바운드' : rule.type;
        
        $tbody.append(`
        <tr>
                <td>${directionInfo}</td>
                <td>${protocolInfo}</td>
                <td>${portInfo}</td>
                <td>${rule.source || '-'}</td>
                <td>${rule.dest || '-'}</td>
                <td><span class="badge ${rule.action === 'ACCEPT' ? 'bg-success' : 'bg-danger'}">${rule.action}</span></td>
                <td>${rule.comment || '-'}${macroInfo}</td>
                <td>
                    <button class="btn btn-outline-danger btn-sm delete-sg-rule-btn" data-rule-id="${rule.pos || index}">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
        </tr>
      `);
    });
  }

// 서비스 매크로 정의 (중복 선언 방지)
if (typeof window.SERVICE_MACROS === 'undefined') {
  window.SERVICE_MACROS = {
    'SSH': { protocol: 'tcp', port: '22' },
    'HTTP': { protocol: 'tcp', port: '80' },
    'HTTPS': { protocol: 'tcp', port: '443' },
    'FTP': { protocol: 'tcp', port: '21' },
    'FTPS': { protocol: 'tcp', port: '990' },
    'SFTP': { protocol: 'tcp', port: '22' },
    'SMTP': { protocol: 'tcp', port: '25' },
    'POP3': { protocol: 'tcp', port: '110' },
    'IMAP': { protocol: 'tcp', port: '143' },
    'DNS': { protocol: 'udp', port: '53' },
    'DHCP': { protocol: 'udp', port: '67,68' },
    'NTP': { protocol: 'udp', port: '123' },
    'MySQL': { protocol: 'tcp', port: '3306' },
    'PostgreSQL': { protocol: 'tcp', port: '5432' },
    'Redis': { protocol: 'tcp', port: '6379' },
    'MongoDB': { protocol: 'tcp', port: '27017' },
    'Elasticsearch': { protocol: 'tcp', port: '9200' },
    'Kafka': { protocol: 'tcp', port: '9092' },
    'RabbitMQ': { protocol: 'tcp', port: '5672' }
  };
}

// 매크로 선택 시 자동 설정 함수
function handleMacroSelection() {
    const selectedMacro = $('#macro-select').val();
    const $protocolSelect = $('#protocol-select');
    const $portInput = $('#port-input');
    
    if (selectedMacro && window.SERVICE_MACROS[selectedMacro]) {
        const macro = window.SERVICE_MACROS[selectedMacro];
        
        // 프로토콜과 포트 자동 설정
        $protocolSelect.val(macro.protocol);
        $portInput.val(macro.port);
        
        // 필드 비활성화
        $protocolSelect.prop('disabled', true);
        $portInput.prop('disabled', true);
        
        // 비활성화된 필드에 시각적 표시
        $protocolSelect.addClass('bg-light');
        $portInput.addClass('bg-light');
        
        console.log(`[firewall.js] 매크로 선택: ${selectedMacro} (${macro.protocol}:${macro.port})`);
    } else {
        // 매크로가 선택되지 않았거나 직접 입력인 경우
        $protocolSelect.prop('disabled', false);
        $portInput.prop('disabled', false);
        
        // 비활성화 표시 제거
        $protocolSelect.removeClass('bg-light');
        $portInput.removeClass('bg-light');
        
        console.log('[firewall.js] 직접 입력 모드');
    }
}

// 이벤트 리스너들
$(function() {
    console.log('[firewall.js] Datacenter Security Group 관리 시스템 초기화');
    
    // 매크로 선택 이벤트
    $(document).on('change', '#macro-select', function() {
        handleMacroSelection();
    });
    
    // Security Group 설정 모달이 열릴 때 매크로 선택 초기화
    $(document).on('shown.bs.modal', '#security-group-config-modal', function() {
        // 매크로 선택 초기화
        $('#macro-select').val('');
        $('#protocol-select').prop('disabled', false).removeClass('bg-light');
        $('#port-input').prop('disabled', false).removeClass('bg-light');
    });
    
    // 페이지 로드 시 자동으로 Security Group 데이터 로드
    if (window.location.hash === '#firewall-groups' || window.location.pathname.includes('firewall')) {
        console.log('[firewall.js] 방화벽 페이지 감지, 데이터 자동 로드');
        window.loadFirewallGroups();
    }
    
    // 새 Security Group 추가 버튼 클릭
    $(document).on('click', '#add-fw-group-btn', function() {
        $('#create-security-group-modal').modal('show');
    });
    
    // Security Group 생성 폼 제출
    $(document).on('submit', '#create-sg-group-form', function(e) {
        e.preventDefault();
        
        const formData = new FormData(this);
        const groupData = {
            name: formData.get('group_name'),
            description: formData.get('description')
        };
        
        console.log('[firewall.js] Security Group 생성:', groupData);
        
        $.ajax({
            url: '/api/firewall/groups',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(groupData),
            success: function(data) {
                console.log('[firewall.js] Security Group 생성 성공:', data);
                
                if (data.success) {
                    $('#create-security-group-modal').modal('hide');
                    $('#create-sg-group-form')[0].reset();
                    
                    // Security Group 목록 새로고침
                    window.loadFirewallGroups();
                    
                    alert('Security Group이 성공적으로 생성되었습니다.');
                } else {
                    alert(data.error || 'Security Group 생성에 실패했습니다.');
                }
            },
            error: function(xhr) {
                console.error('[firewall.js] Security Group 생성 실패:', xhr);
                alert('Security Group 생성에 실패했습니다.');
            }
        });
    });
    
    // Security Group 설정 버튼 클릭
    $(document).on('click', '.sg-config-btn', function() {
        const groupName = $(this).data('group');
        openSecurityGroupConfig(groupName);
    });
    
    // Security Group 삭제 버튼 클릭
    $(document).on('click', '.sg-delete-btn', function() {
        if (!confirm('정말 이 Security Group을 삭제하시겠습니까?')) return;
        
        const groupName = $(this).data('group');
        console.log('[firewall.js] Security Group 삭제:', groupName);
        
        $.ajax({
            url: `/api/firewall/groups/${groupName}`,
            method: 'DELETE',
            success: function(data) {
                console.log('[firewall.js] Security Group 삭제 성공:', data);
                
                if (data.success) {
                    // Security Group 목록 새로고침
                    window.loadFirewallGroups();
                    
                    alert('Security Group이 삭제되었습니다.');
      } else {
                    alert(data.error || 'Security Group 삭제에 실패했습니다.');
                }
            },
            error: function(xhr) {
                console.error('[firewall.js] Security Group 삭제 실패:', xhr);
                alert('Security Group 삭제에 실패했습니다.');
      }
    });
  });

    // Security Group 설정 모달에서 삭제 버튼 클릭
    $(document).on('click', '#delete-sg-group-btn', function() {
        if (!confirm('정말 이 Security Group을 삭제하시겠습니까?')) return;
        
        const groupName = $('#security-group-config-modal').data('group-name');
        console.log('[firewall.js] Security Group 설정 모달에서 삭제:', groupName);
        
    $.ajax({
            url: `/api/firewall/groups/${groupName}`,
            method: 'DELETE',
            success: function(data) {
                console.log('[firewall.js] Security Group 삭제 성공:', data);
                
                if (data.success) {
                    $('#security-group-config-modal').modal('hide');
                    
                    // Security Group 목록 새로고침
                    window.loadFirewallGroups();
                    
                    alert('Security Group이 삭제되었습니다.');
        } else {
                    alert(data.error || 'Security Group 삭제에 실패했습니다.');
        }
            },
            error: function(xhr) {
                console.error('[firewall.js] Security Group 삭제 실패:', xhr);
                alert('Security Group 삭제에 실패했습니다.');
      }
    });
  });

    // Security Group 규칙 추가 폼 제출 (중복 방지)
    $(document).off('submit', '#add-sg-rule-form').on('submit', '#add-sg-rule-form', function(e) {
        e.preventDefault();
        
        const groupName = $('#security-group-config-modal').data('group-name');
        const formData = new FormData(this);
        
        console.log('[firewall.js] Security Group 이름 확인:', groupName);
        
        if (!groupName) {
            alert('Security Group 이름을 찾을 수 없습니다. 페이지를 새로고침하고 다시 시도해주세요.');
            return;
        }
        
        const ruleData = {
            protocol: formData.get('protocol'),
            port: formData.get('port'),
            source_ip: formData.get('source_ip'),
            dest_ip: formData.get('dest_ip'),
            action: formData.get('action'),
            description: formData.get('description'),
            macro: formData.get('macro')  // 매크로 정보 추가
        };
        
        console.log('[firewall.js] Security Group 규칙 추가:', groupName, ruleData);
        console.log('[firewall.js] 전송할 데이터:', JSON.stringify(ruleData, null, 2));
        
        $.ajax({
            url: `/api/firewall/groups/${groupName}/rules`,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(ruleData),
            success: function(data) {
                console.log('[firewall.js] Security Group 규칙 추가 성공:', data);
                
                if (data.success) {
                    $('#add-sg-rule-form')[0].reset();
                    
                    // Security Group 상세 정보 다시 로드
                    loadSecurityGroupDetail(groupName);
                    
                    alert('Security Group 규칙이 추가되었습니다.');
                } else {
                    alert(data.error || 'Security Group 규칙 추가에 실패했습니다.');
                }
            },
            error: function(xhr) {
                console.error('[firewall.js] Security Group 규칙 추가 실패:', xhr);
                alert('Security Group 규칙 추가에 실패했습니다.');
            }
        });
    });
  
    // Security Group 규칙 삭제 버튼 클릭 (중복 방지)
    $(document).off('click', '.delete-sg-rule-btn').on('click', '.delete-sg-rule-btn', function() {
        if (!confirm('정말 이 규칙을 삭제하시겠습니까?')) return;
        
        const groupName = $('#security-group-config-modal').data('group-name');
        const ruleId = $(this).data('rule-id');
        
        console.log('[firewall.js] Security Group 규칙 삭제:', groupName, ruleId);
        
    $.ajax({
            url: `/api/firewall/groups/${groupName}/rules/${ruleId}`,
            method: 'DELETE',
            success: function(data) {
                console.log('[firewall.js] Security Group 규칙 삭제 성공:', data);
                
                if (data.success) {
                    // Security Group 상세 정보 다시 로드
                    loadSecurityGroupDetail(groupName);
                    
                    alert('Security Group 규칙이 삭제되었습니다.');
                } else {
                    alert(data.error || 'Security Group 규칙 삭제에 실패했습니다.');
                }
            },
            error: function(xhr) {
                console.error('[firewall.js] Security Group 규칙 삭제 실패:', xhr);
                alert('Security Group 규칙 삭제에 실패했습니다.');
      }
    });
  });
});
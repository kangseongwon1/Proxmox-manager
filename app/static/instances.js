// instances.js - v1.2 (캐시 무효화)
$(function() {
  // 중복 호출 방지를 위한 플래그
  let isInitialized = false;
  
  console.log('[instances.js] 초기화 시작');
  
  // 알림 시스템은 navigation.js에서 중앙 관리됨
  
  // Datastore 목록 로드
  let datastoreConfig = null;
  function loadDatastores() {
    if (datastoreConfig) return Promise.resolve(datastoreConfig);
    
    return $.get('/api/datastores')
      .then(function(response) {
        if (response.success) {
          datastoreConfig = response;
          console.log('[instances.js] Datastore 목록 로드 완료:', response.datastores);
          
          // DB에 datastore가 없으면 자동으로 새로고침
          if (!response.datastores || response.datastores.length === 0) {
            console.log('[instances.js] DB에 datastore가 없음. 자동으로 새로고침 중...');
            return $.post('/api/datastores/refresh')
              .then(function(refreshResponse) {
                if (refreshResponse.success) {
                  console.log('[instances.js] Datastore 새로고침 완료:', refreshResponse.count, '개');
                  // 새로고침 후 다시 조회
                  return $.get('/api/datastores');
                } else {
                  throw new Error('Datastore 새로고침 실패');
                }
              })
              .then(function(newResponse) {
                if (newResponse.success) {
                  datastoreConfig = newResponse;
                  console.log('[instances.js] 새로고침 후 Datastore 목록 로드 완료:', newResponse.datastores);
                  return newResponse;
                } else {
                  throw new Error('새로고침 후 Datastore 목록 로드 실패');
                }
              });
          }
          
          return response;
        } else {
          throw new Error('Datastore 목록 로드 실패');
        }
      })
      .fail(function(xhr) {
        console.warn('[instances.js] Datastore 목록 로드 실패, 기본값 사용:', xhr);
        // 기본값 사용
        datastoreConfig = {
          success: true,
          datastores: [
            { id: 'local-lvm', name: 'local-lvm', type: 'lvm', is_default_hdd: true },
            { id: 'local', name: 'local', type: 'dir', is_default_ssd: true }
          ],
          default_hdd: 'local-lvm',
          default_ssd: 'local'
        };
        return datastoreConfig;
      });
  }
  
  // 페이지 로드 시 datastore 옵션 초기화
  loadDatastores().then(function(config) {
    $('.disk-datastore').each(function() {
      const $select = $(this);
      $select.empty();
      
      // datastore가 없으면 자동으로 새로고침
      if (!config.datastores || config.datastores.length === 0) {
        console.log('[instances.js] 페이지 로드 시 datastore가 없음. 자동으로 새로고침 중...');
        $.post('/api/datastores/refresh')
          .then(function(refreshResponse) {
            if (refreshResponse.success) {
              console.log('[instances.js] 페이지 로드 시 Datastore 새로고침 완료:', refreshResponse.count, '개');
              // 새로고침 후 다시 조회
              return $.get('/api/datastores');
            } else {
              throw new Error('Datastore 새로고침 실패');
            }
          })
          .then(function(newResponse) {
            if (newResponse.success) {
              console.log('[instances.js] 페이지 로드 시 새로고침 후 Datastore 목록 로드 완료:', newResponse.datastores);
              // 새로고침된 데이터로 옵션 생성
              newResponse.datastores.forEach(function(datastore) {
                const isSelected = datastore.id === newResponse.default_hdd ? 'selected' : '';
                const typeLabel = datastore.type === 'lvm' ? 'LVM' : 
                                 datastore.type === 'dir' ? 'Directory' : 
                                 datastore.type === 'nfs' ? 'NFS' : 
                                 datastore.type.toUpperCase();
                
                $select.append(`<option value="${datastore.id}" ${isSelected}>${datastore.name} (${typeLabel})</option>`);
              });
            } else {
              throw new Error('새로고침 후 Datastore 목록 로드 실패');
            }
          })
          .fail(function(error) {
            console.error('[instances.js] 페이지 로드 시 Datastore 새로고침 실패:', error);
            // 실패 시 기본값 사용
            $select.append('<option value="local-lvm" selected>local-lvm (LVM)</option>');
            $select.append('<option value="local">local (Directory)</option>');
          });
      } else {
        // 기존 로직
        config.datastores.forEach(function(datastore) {
          const isSelected = datastore.id === config.default_hdd ? 'selected' : '';
          const typeLabel = datastore.type === 'lvm' ? 'LVM' : 
                           datastore.type === 'dir' ? 'Directory' : 
                           datastore.type === 'nfs' ? 'NFS' : 
                           datastore.type.toUpperCase();
          
          $select.append(`<option value="${datastore.id}" ${isSelected}>${datastore.name} (${typeLabel})</option>`);
        });
      }
    });
  });
  
  // SSE 전환으로 서버 상태 폴링 제거
  let isBulkOperationInProgress = false; // 일괄 작업 진행 상태 플래그
  let taskConfig = null; // Task 설정 정보
  
  // Task 설정 정보 로드
  function loadTaskConfig() {
    if (taskConfig) return Promise.resolve(taskConfig);
    
    return $.get('/api/tasks/config')
      .then(function(config) {
        taskConfig = config;
        console.log('[instances.js] Task 설정 로드 완료:', config);
        return config;
      })
      .fail(function(xhr) {
        console.warn('[instances.js] Task 설정 로드 실패, 기본값 사용:', xhr);
        // 기본값 설정
        taskConfig = {
          timeout: 18000,
          timeout_hours: 5,
          polling_interval: 5000
        };
        return taskConfig;
      });
  }
  
  // 디스크 추가 시 datastore 옵션 동적 생성
  function createDiskDatastoreSelect(datastores, defaultHdd) {
    let options = '';
    
    datastores.forEach(function(datastore) {
      const isSelected = datastore.id === defaultHdd ? 'selected' : '';
      const typeLabel = datastore.type === 'lvm' ? 'LVM' : 
                       datastore.type === 'dir' ? 'Directory' : 
                       datastore.type === 'nfs' ? 'NFS' : 
                       datastore.type.toUpperCase();
      
      options += `<option value="${datastore.id}" ${isSelected}>${datastore.name} (${typeLabel})</option>`;
    });
    
    return `<select class="form-select disk-datastore">${options}</select>`;
  }
  
  function startServerStatusPolling() {
    console.log('[instances.js] SSE 전환으로 서버 상태 폴링 비활성화');
    // 폴링 대신 SSE를 통해 실시간 업데이트
  }
  
  function stopServerStatusPolling() {
    console.log('[instances.js] SSE 전환으로 서버 상태 폴링 비활성화');
    // 폴링 대신 SSE를 통해 실시간 업데이트
  }
  
  // 작업 후 서버 상태 업데이트 함수
  function updateServerStatusAfterAction(serverName, newStatus) {
    console.log(`[instances.js] 서버 상태 업데이트: ${serverName} → ${newStatus}`);
    
    // 해당 서버의 상태 배지 업데이트
    const $serverRow = $(`.server-row[data-server="${serverName}"]`);
    if ($serverRow.length > 0) {
      let statusBadge = '';
      switch(newStatus) {
        case 'running': 
          statusBadge = '<span class="status-badge status-success">실행 중</span>';
          break;
        case 'stopped':
          statusBadge = '<span class="status-badge status-stopped">중지됨</span>';
          break;
        case 'paused':
          statusBadge = '<span class="status-badge status-warning">일시정지</span>';
          break;
        default:
          statusBadge = '<span class="status-badge status-unknown">' + newStatus + '</span>';
      }
      
      // 상태 배지 업데이트
      $serverRow.find('.server-status').html(statusBadge);
      $serverRow.data('status', newStatus);
      
      // 작업 버튼 상태 업데이트
      updateServerActionButtons($serverRow, newStatus);
      
      console.log(`[instances.js] 서버 ${serverName} 상태 업데이트 완료: ${newStatus}`);
    }
  }
  
  // 작업 완료 시 알림 표시 함수
  function showTaskCompletionNotification(taskType, serverName, status, message) {
    let severity = 'info';
    let title = '';
    
    switch(taskType) {
      case 'create':
        title = `서버 생성 ${status === 'success' ? '완료' : '실패'}`;
        severity = status === 'success' ? 'success' : 'error';
        break;
      case 'start':
        title = `서버 시작 ${status === 'success' ? '완료' : '실패'}`;
        severity = status === 'success' ? 'success' : 'error';
        break;
      case 'stop':
        title = `서버 중지 ${status === 'success' ? '완료' : '실패'}`;
        severity = status === 'success' ? 'success' : 'error';
        break;
      case 'delete':
        title = `서버 삭제 ${status === 'success' ? '완료' : '실패'}`;
        severity = status === 'success' ? 'success' : 'error';
        break;
      default:
        title = `작업 ${status === 'success' ? '완료' : '실패'}`;
        severity = status === 'success' ? 'success' : 'error';
    }
    
    window.addNewNotification(severity, title, message);
  }
  
  // 서버 작업 버튼 상태 업데이트
  function updateServerActionButtons($serverRow, status) {
    const $startBtn = $serverRow.find('.start-btn');
    const $stopBtn = $serverRow.find('.stop-btn');
    const $rebootBtn = $serverRow.find('.reboot-btn');
    
    // 모든 버튼 활성화
    $startBtn.prop('disabled', false).removeClass('btn-secondary').addClass('btn-success');
    $stopBtn.prop('disabled', false).removeClass('btn-secondary').addClass('btn-danger');
    $rebootBtn.prop('disabled', false).removeClass('btn-secondary').addClass('btn-warning');
    
    // 상태에 따른 버튼 비활성화
    switch(status) {
      case 'running':
        $startBtn.prop('disabled', true).removeClass('btn-success').addClass('btn-secondary');
        break;
      case 'stopped':
        $stopBtn.prop('disabled', true).removeClass('btn-danger').addClass('btn-secondary');
        $rebootBtn.prop('disabled', true).removeClass('btn-warning').addClass('btn-secondary');
        break;
      case 'paused':
        $stopBtn.prop('disabled', true).removeClass('btn-danger').addClass('btn-secondary');
        break;
    }
  }
  
  // 전역 함수로 노출
  window.updateServerStatusAfterAction = updateServerStatusAfterAction;
  
  // 숫자를 소수점 2자리까지 포맷팅하는 함수
  function format2f(num) {
    return parseFloat(num).toFixed(2);
  }

  
  // 서버 역할 매핑
  window.dashboardRoleMap = {
    'web': '웹서버(Nginx)',
    'was': 'WAS(Python3.12)',
    'java': 'JAVA(17.0.7)',
    'search': '검색(Elasticsearch7)',
    'ftp': 'FTP(vsftpd)',
    'db': 'DB(MariaDB10.11)'
  };
  
  // 알림 시스템은 navigation.js에서 중앙 관리됨
  
  // 알림 모달 함수
  function alertModal(message) {
    alert(message);
  }

  // 서버 알림 가져오기 공통 함수 (SSE로 대체됨)
  function fetchAndDisplayNotifications(severity = 'success', fallbackMessage = '') {
    // SSE를 통해 실시간 알림 수신하므로 폴링 불필요
    console.log(`[instances.js] SSE 전환으로 알림 폴링 비활성화`);
    if (fallbackMessage) {
      addSystemNotification(severity, '작업 완료', fallbackMessage);
    }
  }
  
  // 서버 생성 탭으로 전환
  window.switchToCreateTab = function() {
    const createTab = document.getElementById('create-tab');
    if (createTab) {
      createTab.click();
    }
  };
  
  // 서버 설정 모달 열기
  window.openServerConfig = function(serverName) {
    console.log(`[instances.js] 서버 설정 모달 열기: ${serverName}`);
    
    // 방화벽 그룹 목록을 먼저 가져오기
    $.get('/api/firewall/groups', function(fwData) {
      console.log('[instances.js] 방화벽 그룹 API 응답:', fwData);
      const firewallGroups = fwData.groups || [];
      
      // 방화벽 그룹 드롭다운 옵션 생성
      let fwGroupOptions = '<option value="">그룹 없음</option>';
      firewallGroups.forEach(group => {
        fwGroupOptions += `<option value="${group.name}">${group.name} - ${group.description}</option>`;
      });
      $('#server-firewall-group').html(fwGroupOptions);
      
      // 서버 설정 정보 로드
      $.ajax({
        url: `/api/server/config/${serverName}`,
        method: 'GET',
        success: function(res) {
          if (res.success) {
            const config = res.config;
            
            // 모달에 데이터 설정
            $('#server-config-modal .modal-title').text(`서버 설정: ${serverName}`);
            $('#server-name').val(config.name);
            $('#server-vmid').val(config.vmid);
            $('#server-node').val(config.node);
            $('#server-status').val(config.status);
            
            // CPU 설정
            $('#cpu-cores').val(config.cpu.cores);
            $('#cpu-cores').attr('data-original', config.cpu.cores);
            $('#cpu-sockets').val(config.cpu.sockets);
            $('#cpu-type').val(config.cpu.type);
            
            // 메모리 설정
            $('#memory-size').val(config.memory.size_mb);
            $('#memory-size').attr('data-original', config.memory.size_mb);
            $('#memory-balloon').val(config.memory.balloon);
            
            // 역할 및 방화벽 그룹
            $('#server-role').val(config.role);
            $('#server-role').attr('data-original', config.role || '');
            $('#server-firewall-group').val(config.firewall_group);
            $('#server-firewall-group').attr('data-original', config.firewall_group || '');
            
            // 설명 및 태그
            $('#server-description').val(config.description);
            $('#server-tags').val(config.tags);
            
            // 디스크 목록 표시
            renderDiskList(config.disks);
            
            // 사용 가능한 디스크 번호 제안
            suggestAvailableDiskNumber(config.disks);
            
            // 모달 표시
            $('#server-config-modal').modal('show');
          } else {
            alert(`서버 설정 로드 실패: ${res.error}`);
          }
        },
        error: function(xhr) {
          console.error('[instances.js] 서버 설정 로드 실패:', xhr);
          alert('서버 설정을 불러올 수 없습니다.');
        }
      });
    }).fail(function(xhr) {
      console.error('[instances.js] 방화벽 그룹 로드 실패:', xhr);
      // 방화벽 그룹 로드 실패 시에도 서버 설정은 계속 진행
      $('#server-firewall-group').html('<option value="">그룹 없음</option>');
      
      // 서버 설정 정보 로드 (방화벽 그룹 없이)
      $.ajax({
        url: `/api/server/config/${serverName}`,
        method: 'GET',
        success: function(res) {
          if (res.success) {
            const config = res.config;
            
            // 모달에 데이터 설정 (방화벽 그룹 제외)
            $('#server-config-modal .modal-title').text(`서버 설정: ${serverName}`);
            $('#server-name').val(config.name);
            $('#server-vmid').val(config.vmid);
            $('#server-node').val(config.node);
            $('#server-status').val(config.status);
            
            // CPU 설정
            $('#cpu-cores').val(config.cpu.cores);
            $('#cpu-cores').attr('data-original', config.cpu.cores);
            $('#cpu-sockets').val(config.cpu.sockets);
            $('#cpu-type').val(config.cpu.type);
            
            // 메모리 설정
            $('#memory-size').val(config.memory.size_mb);
            $('#memory-size').attr('data-original', config.memory.size_mb);
            $('#memory-balloon').val(config.memory.balloon);
            
            // 역할 (방화벽 그룹은 기본값으로 설정)
            $('#server-role').val(config.role);
            $('#server-firewall-group').attr('data-original', config.firewall_group || '');
            $('#server-firewall-group').val('');
            
            // 설명 및 태그
            $('#server-description').val(config.description);
            $('#server-tags').val(config.tags);
            
            // 디스크 목록 표시
            renderDiskList(config.disks);
            
            // 사용 가능한 디스크 번호 제안
            suggestAvailableDiskNumber(config.disks);
            
            // 모달 표시
            $('#server-config-modal').modal('show');
          } else {
            alert(`서버 설정 로드 실패: ${res.error}`);
          }
        },
        error: function(xhr) {
          console.error('[instances.js] 서버 설정 로드 실패:', xhr);
          alert('서버 설정을 불러올 수 없습니다.');
        }
      });
    });
  };
  
  // 사용 가능한 디스크 번호 제안
  function suggestAvailableDiskNumber(disks) {
    const selectedType = $('#new-disk-type').val();
    const existingNumbers = new Set();
    
    // 현재 선택된 타입의 기존 디스크 번호들 수집
    disks.forEach(disk => {
      if (disk.device.startsWith(selectedType)) {
        const number = disk.device.replace(selectedType, '');
        if (!isNaN(number)) {
          existingNumbers.add(parseInt(number));
        }
      }
    });
    
    // 사용 가능한 번호 찾기
    let availableNumber = 0;
    while (existingNumbers.has(availableNumber)) {
      availableNumber++;
    }
    
    // 제안 번호 설정
    $('#new-disk-number').val(availableNumber);
  }
  
  // 디스크 타입 변경 시 번호 제안 업데이트
  $('#new-disk-type').on('change', function() {
    const disks = [];
    $('#disk-list .d-flex').each(function() {
      const deviceText = $(this).find('strong').text();
      const storageText = $(this).find('strong').parent().text().match(/\(([^)]+)\)/)[1];
      const sizeText = $(this).find('small').text().match(/크기: (\d+)GB/)[1];
      
      disks.push({
        device: deviceText,
        storage: storageText,
        size_gb: parseInt(sizeText)
      });
    });
    
    suggestAvailableDiskNumber(disks);
  });
  
  // 디스크 목록 렌더링
  function renderDiskList(disks) {
    const diskList = $('#disk-list');
    diskList.empty();
    
    if (!disks || disks.length === 0) {
      diskList.html('<div class="text-muted">디스크가 없습니다.</div>');
      return;
    }
    
    disks.forEach((disk, index) => {
      const diskHtml = `
        <div class="d-flex justify-content-between align-items-center mb-2 p-2 border-bottom">
          <div>
            <strong>${disk.device}</strong> (${disk.storage})
            <br><small class="text-muted">크기: ${disk.size_gb}GB</small>
          </div>
          <button type="button" class="btn btn-danger btn-sm" onclick="removeDisk('${disk.device}')">
            <i class="fas fa-trash"></i> 삭제
          </button>
        </div>
      `;
      diskList.append(diskHtml);
    });
  }
  
  // 새 디스크 추가
  window.addNewDisk = function() {
    const type = $('#new-disk-type').val();
    const number = $('#new-disk-number').val();
    const storage = $('#new-disk-storage').val();
    const size = $('#new-disk-size').val();
    
    if (!size || size < 1) {
      alert('디스크 크기를 입력해주세요.');
      return;
    }
    
    if (number === '' || number < 0 || number > 15) {
      alert('디스크 번호를 입력해주세요. (0-15)');
      return;
    }
    
    const serverName = $('#server-name').val();
    const diskData = {
      type: type,
      number: parseInt(number),
      storage: storage,
      size_gb: parseInt(size)
    };
    
    console.log(`[instances.js] 새 디스크 추가: ${serverName}`, diskData);
    
    $.ajax({
      url: `/api/server/disk/${serverName}`,
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify(diskData),
      success: function(res) {
        if (res.success) {
          alert('디스크가 추가되었습니다. 서버를 중지 후 재시작하면 적용됩니다.');
          // 디스크 목록 새로고침
          openServerConfig(serverName);
        } else {
          alert(`디스크 추가 실패: ${res.error}`);
        }
      },
      error: function(xhr) {
        console.error('[instances.js] 디스크 추가 실패:', xhr);
        alert('디스크 추가에 실패했습니다.');
      }
    });
  };
  
  // 디스크 삭제
  window.removeDisk = function(device) {
    if (!confirm(`디스크 ${device}를 삭제하시겠습니까?\n\n⚠️ 주의: 이 작업은 되돌릴 수 없습니다.`)) {
      return;
    }
    
    const serverName = $('#server-name').val();
    
    console.log(`[instances.js] 디스크 삭제: ${serverName} - ${device}`);
    
    $.ajax({
      url: `/api/server/disk/${serverName}/${device}`,
      method: 'DELETE',
      success: function(res) {
        if (res.success) {
          alert('디스크가 삭제되었습니다. 서버를 중지 후 재시작하면 적용됩니다.');
          // 디스크 목록 새로고침
          openServerConfig(serverName);
        } else {
          alert(`디스크 삭제 실패: ${res.error}`);
        }
      },
      error: function(xhr) {
        console.error('[instances.js] 디스크 삭제 실패:', xhr);
        alert('디스크 삭제에 실패했습니다.');
      }
    });
  };
  
  // 서버 설정 저장
  window.saveServerConfig = function() {
    const serverName = $('#server-name').val();
    
    // 현재 설정값과 변경된 설정값 비교
    const currentCpu = parseInt($('#cpu-cores').attr('data-original') || $('#cpu-cores').val());
    const currentMemory = parseInt($('#memory-size').attr('data-original') || $('#memory-size').val());
    const newCpu = parseInt($('#cpu-cores').val());
    const newMemory = parseInt($('#memory-size').val());
    
    const configData = {
      cpu: {
        cores: newCpu,
        sockets: parseInt($('#cpu-sockets').val()),
        type: $('#cpu-type').val()
      },
      memory: {
        size_mb: newMemory,
        balloon: parseInt($('#memory-balloon').val())
      },
      role: $('#server-role').val(),
      firewall_group: $('#server-firewall-group').val(),
      description: $('#server-description').val(),
      tags: $('#server-tags').val()
    };
    
    console.log(`[instances.js] 서버 설정 저장: ${serverName}`, configData);
    
    // CPU/메모리 변경 감지
    const needsReboot = (currentCpu !== newCpu) || (currentMemory !== newMemory);
    
    // 방화벽 그룹 변경 감지
    const selectedFirewallGroup = $('#server-firewall-group').val();
    const currentFirewallGroup = $('#server-firewall-group').attr('data-original') || '';
    const hasFirewallGroupChange = selectedFirewallGroup && selectedFirewallGroup !== '';
    const isRemovingFirewallGroup = (selectedFirewallGroup === '' || selectedFirewallGroup === '그룹 없음') && currentFirewallGroup !== '';
    
    // 역할 변경 감지
    const selectedRole = $('#server-role').val();
    const currentRole = $('#server-role').attr('data-original') || '';
    const hasRoleChange = selectedRole !== currentRole;
    
    // 1단계: 기본 서버 설정 저장
    $.ajax({
      url: `/api/server/config/${serverName}`,
      method: 'PUT',
      contentType: 'application/json',
      data: JSON.stringify(configData),
      success: function(res) {
        if (res.success) {
          console.log('[instances.js] 기본 서버 설정 저장 성공');
          
          // 2단계: 방화벽 그룹 처리
          if (isRemovingFirewallGroup) {
            // 방화벽 그룹 제거 (실제로 설정된 경우에만)
            console.log('[instances.js] 방화벽 그룹 제거 시작');
            
            $.ajax({
              url: `/api/remove_firewall_group/${serverName}`,
              method: 'POST',
              contentType: 'application/json',
              success: function(fwRes) {
                if (fwRes.success) {
                  console.log('[instances.js] 방화벽 그룹 제거 성공');
                  alert(`서버 설정이 성공적으로 저장되었습니다.\n\n✅ 방화벽 그룹이 제거되었습니다.`);
                } else {
                  console.error('[instances.js] 방화벽 그룹 제거 실패:', fwRes.error);
                  alert(`서버 설정은 저장되었지만 방화벽 그룹 제거에 실패했습니다: ${fwRes.error}`);
                }
                
                // 모달 닫기 및 서버 목록 새로고침
                $('#server-config-modal').modal('hide');
                loadActiveServers();
              },
              error: function(xhr) {
                console.error('[instances.js] 방화벽 그룹 제거 실패:', xhr);
                let errorMsg = '알 수 없는 오류';
                if (xhr.responseJSON?.error) {
                  errorMsg = xhr.responseJSON.error;
                }
                alert(`서버 설정은 저장되었지만 방화벽 그룹 제거에 실패했습니다: ${errorMsg}`);
                
                // 모달 닫기 및 서버 목록 새로고침
                $('#server-config-modal').modal('hide');
                loadActiveServers();
              }
            });
          } else if (hasFirewallGroupChange) {
            // 방화벽 그룹 적용
            console.log(`[instances.js] 방화벽 그룹 적용 시작: ${selectedFirewallGroup}`);
            
            $.ajax({
              url: `/api/apply_security_group/${serverName}`,
              method: 'POST',
              contentType: 'application/json',
              data: JSON.stringify({
                security_group: selectedFirewallGroup
              }),
              success: function(fwRes) {
                if (fwRes.success) {
                  console.log('[instances.js] 방화벽 그룹 적용 성공');
                  alert(`서버 설정이 성공적으로 저장되었습니다.\n\n✅ 방화벽 그룹 '${selectedFirewallGroup}'이 적용되었습니다.`);
                } else {
                  console.error('[instances.js] 방화벽 그룹 적용 실패:', fwRes.error);
                  alert(`서버 설정은 저장되었지만 방화벽 그룹 적용에 실패했습니다: ${fwRes.error}`);
                }
                
                // 모달 닫기 및 서버 목록 새로고침
                $('#server-config-modal').modal('hide');
                loadActiveServers();
              },
              error: function(xhr) {
                console.error('[instances.js] 방화벽 그룹 적용 실패:', xhr);
                let errorMsg = '알 수 없는 오류';
                if (xhr.responseJSON?.error) {
                  errorMsg = xhr.responseJSON.error;
                }
                alert(`서버 설정은 저장되었지만 방화벽 그룹 적용에 실패했습니다: ${errorMsg}`);
                
                // 모달 닫기 및 서버 목록 새로고침
                $('#server-config-modal').modal('hide');
                loadActiveServers();
              }
            });
          } else {
            // 방화벽 그룹이 선택되지 않은 경우
            if (hasRoleChange) {
              // 역할 변경 시 Ansible API 호출
              console.log(`[instances.js] 역할 변경 감지: ${currentRole} → ${selectedRole}`);
              
              $.ajax({
                url: `/api/assign_role/${serverName}`,
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                  role: selectedRole
                }),
                success: function(roleRes) {
                  if (roleRes.success) {
                    console.log('[instances.js] 역할 할당 성공');
                    
                    // 역할 제거인지 확인
                    if (!selectedRole || selectedRole === '') {
                      alert(`서버 설정이 성공적으로 저장되었습니다.\n\n✅ 역할이 '${currentRole}'에서 제거되었습니다.`);
                    } else {
                      alert(`서버 설정이 성공적으로 저장되었습니다.\n\n✅ 역할이 '${currentRole}'에서 '${selectedRole}'로 변경되었습니다.`);
                    }

                    // Ansible 비동기 완료 알림을 한시적으로 폴링하여 즉시 표시
                    if (window.watchAnsibleRoleNotification) {
                      window.watchAnsibleRoleNotification(serverName);
                    }
                  } else {
                    console.error('[instances.js] 역할 할당 실패:', roleRes.error);
                    alert(`서버 설정은 저장되었지만 역할 할당에 실패했습니다: ${roleRes.error}`);
                  }
                  
                  // 모달 닫기 및 서버 목록 새로고침
                  $('#server-config-modal').modal('hide');
                  loadActiveServers();
                },
                error: function(xhr) {
                  console.error('[instances.js] 역할 할당 실패:', xhr);
                  let errorMsg = '알 수 없는 오류';
                  if (xhr.responseJSON?.error) {
                    errorMsg = xhr.responseJSON.error;
                  }
                  alert(`서버 설정은 저장되었지만 역할 할당에 실패했습니다: ${errorMsg}`);
                  
                  // 모달 닫기 및 서버 목록 새로고침
                  $('#server-config-modal').modal('hide');
                  loadActiveServers();
                }
              });
            } else {
              // 역할 변경이 없는 경우
              $('#server-config-modal').modal('hide');
              
              if (needsReboot) {
                alert('서버 설정이 성공적으로 저장되었습니다.\n\n⚠️ CPU 또는 메모리 설정이 변경되었습니다.\n변경사항을 적용하기 위해 서버를 중지 후 재시작합니다...');
              
                // 중지 → 재시작 실행
                $.ajax({
                  url: `/api/servers/${serverName}/stop`,
                  method: 'POST',
                  success: function(stopRes) {
                    if (stopRes.success) {
                      alert('서버가 중지되었습니다. 잠시 후 재시작됩니다...');
                      
                      // 5초 후 재시작
                      setTimeout(function() {
                        $.ajax({
                          url: `/api/servers/${serverName}/start`,
                          method: 'POST',
                          success: function(startRes) {
                            if (startRes.success) {
                              alert('서버가 재시작되었습니다. 설정 변경사항이 적용됩니다.');
                            } else {
                              alert(`재시작 실패: ${startRes.error}`);
                            }
                          },
                          error: function(xhr) {
                            console.error('[instances.js] 재시작 실패:', xhr);
                            alert('서버 재시작에 실패했습니다.');
                          }
                        });
                      }, 5000); // 5초 대기
                      
                    } else {
                      alert(`중지 실패: ${stopRes.error}`);
                    }
                  },
                  error: function(xhr) {
                    console.error('[instances.js] 중지 실패:', xhr);
                    alert('서버 중지에 실패했습니다.');
                  }
                });
              } else {
                alert('서버 설정이 성공적으로 저장되었습니다.');
              }
              
              // 서버 목록 새로고침
              loadActiveServers();
            }
          }
        } else {
          alert(`서버 설정 저장 실패: ${res.error}`);
        }
      },
      error: function(xhr) {
        console.error('[instances.js] 서버 설정 저장 실패:', xhr);
        alert('서버 설정 저장에 실패했습니다.');
      }
    });
  };
  
  // 서버 로그 보기
  window.viewServerLogs = function(serverName) {
    console.log(`[instances.js] 서버 로그 보기: ${serverName}`);
    
    // 로그 타입 선택 모달 표시
    $('#log-type-modal .modal-title').text(`로그 보기: ${serverName}`);
    $('#log-server-name').val(serverName);
    $('#log-type-modal').modal('show');
  };
  
  // 로그 조회 실행
  window.loadServerLogs = function() {
    const serverName = $('#log-server-name').val();
    const logType = $('#log-type-select').val();
    const lines = $('#log-lines').val();
    
    console.log(`[instances.js] 로그 조회: ${serverName}, 타입: ${logType}, 라인: ${lines}`);
    
    // 로그 조회 API 호출
    $.ajax({
      url: `/api/server/logs/${serverName}`,
      method: 'GET',
      data: {
        type: logType,
        lines: lines
      },
      success: function(res) {
        if (res.success && res.logs) {
          const logData = res.logs;
          
          // 로그 내용 표시 (안전한 접근)
          $('#log-content-modal .modal-title').text(`${serverName} - ${logType} 로그`);
          $('#log-content').text(logData.content || '로그 내용이 없습니다.');
          $('#log-timestamp').text(`조회 시간: ${logData.timestamp || '알 수 없음'}`);
          
          $('#log-type-modal').modal('hide');
          $('#log-content-modal').modal('show');
        } else {
          const errorMsg = res.error || '로그 데이터를 받을 수 없습니다.';
          alert(`로그 조회 실패: ${errorMsg}`);
        }
      },
      error: function(xhr) {
        console.error('[instances.js] 로그 조회 실패:', xhr);
        alert('로그를 불러올 수 없습니다.');
      }
    });
  };
  
  // 서버 백업
  window.backupServer = function(serverName) {
    console.log(`[instances.js] 서버 백업: ${serverName}`);
    
    // 백업 설정 모달 표시
    $('#backup-modal .modal-title').text(`서버 백업: ${serverName}`);
    $('#backup-server-name').val(serverName);
    $('#backup-description').val(`Backup of ${serverName} - ${new Date().toLocaleString()}`);
    $('#backup-modal').modal('show');
  };
  
  // 백업 상태 확인 및 서버 작업 차단 관리
  let backupPollingIntervals = {}; // 백업 상태 폴링 인터벌 관리
  
  // 서버가 백업 중인지 확인
  function isServerBackingUp(serverName) {
    return window.backingUpServers && window.backingUpServers.includes(serverName);
  }
  
  // 백업 중인 서버 목록 관리
  window.backingUpServers = window.backingUpServers || [];
  
  // 서버 작업 버튼 상태 업데이트 (백업 중이면 비활성화)
  function updateBackupActionButtons(serverName, isBackingUp) {
    const $serverRow = $(`.server-row[data-server="${serverName}"]`);
    if ($serverRow.length > 0) {
      const $actionButtons = $serverRow.find('.table-actions button');
      const $detailButtons = $(`.server-detail-row[data-server="${serverName}"] button`);
      
      if (isBackingUp) {
        // 백업 중이면 모든 작업 버튼 비활성화
        $actionButtons.prop('disabled', true);
        $detailButtons.prop('disabled', true);
        
        // 백업 중 표시 추가
        $serverRow.addClass('backup-in-progress');
      } else {
        // 백업 완료되면 원래 상태로 복원
        $serverRow.removeClass('backup-in-progress');
        
        // 서버 상태에 따른 버튼 활성화/비활성화 (기존 함수 호출)
        const serverStatus = $serverRow.data('status');
        updateServerActionButtons($serverRow, serverStatus);
      }
    }
  }
  
  // 모든 서버의 백업 상태 확인
  function checkAllBackupStatus() {
    console.log('[instances.js] 모든 서버 백업 상태 확인 시작');
    
    $.ajax({
      url: '/api/server/backup/status',
      method: 'GET',
      success: function(res) {
        console.log('[instances.js] 전체 백업 상태 API 응답:', res);
        
        if (res.success && res.backup_status) {
          console.log('[instances.js] 백업 중인 서버들:', Object.keys(res.backup_status));
          
          // 백업 중인 서버들 처리
          for (const [serverName, status] of Object.entries(res.backup_status)) {
            console.log(`[instances.js] 백업 상태 확인: ${serverName} - ${status.status}`);
            
            if (status.status === 'running') {
              console.log(`[instances.js] 진행 중인 백업 발견: ${serverName}`);
              
              // 백업 중인 서버 목록에 추가
              if (!window.backingUpServers.includes(serverName)) {
                window.backingUpServers.push(serverName);
                console.log(`[instances.js] 백업 중인 서버 목록에 추가: ${serverName}`);
              }
              
              // UI 업데이트
              updateBackupActionButtons(serverName, true);
              
              // 폴링 시작 (이미 시작되지 않은 경우에만)
              if (!backupPollingIntervals[serverName]) {
                console.log(`[instances.js] 백업 폴링 시작: ${serverName}`);
                startBackupStatusPolling(serverName, status.backup_id);
              } else {
                console.log(`[instances.js] 백업 폴링 이미 실행 중: ${serverName}`);
              }
            }
          }
        } else {
          console.log('[instances.js] 백업 중인 서버 없음');
        }
      },
      error: function(xhr) {
        console.error('[instances.js] 백업 상태 확인 실패:', xhr);
        console.error('[instances.js] 응답 텍스트:', xhr.responseText);
      }
    });
  }
  
  // 백업 상태 폴링 시작
  function startBackupStatusPolling(serverName, backupId) {
    console.log(`[instances.js] 백업 상태 폴링 시작: ${serverName} (${backupId})`);
    
    // 백업 중인 서버 목록에 추가
    if (!window.backingUpServers.includes(serverName)) {
      window.backingUpServers.push(serverName);
      console.log(`[instances.js] 백업 중인 서버 목록에 추가: ${serverName}`);
    }
    
    // 서버 작업 버튼 비활성화
    updateBackupActionButtons(serverName, true);
    
    // 30초마다 상태 확인
    const pollInterval = setInterval(function() {
      console.log(`[instances.js] 백업 상태 폴링 실행: ${serverName}`);
      
      $.ajax({
        url: `/api/server/backup/status/${serverName}`,
        method: 'GET',
        success: function(res) {
          console.log(`[instances.js] 백업 상태 API 응답: ${serverName}`, res);
          
          if (res.success && res.backup_status) {
            const status = res.backup_status.status;
            const message = res.backup_status.message;
            
            console.log(`[instances.js] 백업 상태: ${serverName} - ${status} - ${message}`);
            
            if (status === 'completed') {
              // 백업 완료
              console.log(`[instances.js] 백업 완료 감지: ${serverName}`);
              addSystemNotification('success', '백업 완료', `서버 ${serverName} 백업이 완료되었습니다.`);
              stopBackupStatusPolling(serverName);
              
            } else if (status === 'failed') {
              // 백업 실패
              console.log(`[instances.js] 백업 실패 감지: ${serverName}`);
              addSystemNotification('error', '백업 실패', `서버 ${serverName} 백업이 실패했습니다: ${message}`);
              stopBackupStatusPolling(serverName);
            } else if (status === 'running') {
              // 백업 진행 중
              console.log(`[instances.js] 백업 진행 중: ${serverName}`);
            }
            // 'running' 상태면 계속 폴링
          } else {
            // 백업 상태가 없으면 완료된 것으로 간주
            console.log(`[instances.js] 백업 상태 없음 - 완료된 것으로 간주: ${serverName}`);
            stopBackupStatusPolling(serverName);
          }
        },
        error: function(xhr) {
          console.error(`[instances.js] 백업 상태 조회 실패: ${serverName}`, xhr);
          console.error(`[instances.js] 응답 텍스트:`, xhr.responseText);
          // 에러 시에도 폴링 중지
          stopBackupStatusPolling(serverName);
        }
      });
    }, 30000); // 30초마다 확인
    
    // 폴링 인터벌 저장
    backupPollingIntervals[serverName] = pollInterval;
    console.log(`[instances.js] 백업 폴링 인터벌 저장: ${serverName}`, pollInterval);
  }
  
  // 백업 상태 폴링 중지
  function stopBackupStatusPolling(serverName) {
    console.log(`[instances.js] 백업 상태 폴링 중지: ${serverName}`);
    
    // 폴링 인터벌 정리
    if (backupPollingIntervals[serverName]) {
      clearInterval(backupPollingIntervals[serverName]);
      delete backupPollingIntervals[serverName];
    }
    
    // 백업 중인 서버 목록에서 제거
    const index = window.backingUpServers.indexOf(serverName);
    if (index > -1) {
      window.backingUpServers.splice(index, 1);
    }
    
    // 서버 작업 버튼 활성화
    updateBackupActionButtons(serverName, false);
  }
  
  // 백업 알림 처리는 navigation.js에서 중앙 관리됨
  
  // 비동기 백업 태스크 상태 폴링 (사용하지 않음 - SSE로 대체)
  function startBackupTaskPolling(serverName, taskId) {
    console.log(`[instances.js] 백업 태스크 폴링 시작: ${serverName}, task_id: ${taskId}`);
    
    // 백업 중인 서버 목록에 추가
    if (window.backingUpServers.indexOf(serverName) === -1) {
      window.backingUpServers.push(serverName);
    }
    
    // 서버 작업 버튼 비활성화
    updateBackupActionButtons(serverName, true);
    
    // 태스크 상태 폴링
    const pollInterval = setInterval(() => {
      $.ajax({
        url: `/api/tasks/${taskId}/status`,
        method: 'GET',
        success: function(res) {
          console.log(`[instances.js] 백업 태스크 상태:`, res);
          
          if (res.state === 'SUCCESS') {
            console.log(`[instances.js] 백업 태스크 완료: ${serverName}`);
            clearInterval(pollInterval);
            delete backupPollingIntervals[serverName];
            
            // 백업 중인 서버 목록에서 제거
            const index = window.backingUpServers.indexOf(serverName);
            if (index > -1) {
              window.backingUpServers.splice(index, 1);
            }
            
            // 서버 작업 버튼 활성화
            updateBackupActionButtons(serverName, false);
            
            // 성공 알림
            addSystemNotification('success', '백업 완료', `서버 ${serverName} 백업이 완료되었습니다.`);
            
            // 백업 목록 새로고침
            if (typeof loadBackupList === 'function') {
              loadBackupList(serverName);
            }
          } else if (res.state === 'FAILURE') {
            console.log(`[instances.js] 백업 태스크 실패: ${serverName}`);
            clearInterval(pollInterval);
            delete backupPollingIntervals[serverName];
            
            // 백업 중인 서버 목록에서 제거
            const index = window.backingUpServers.indexOf(serverName);
            if (index > -1) {
              window.backingUpServers.splice(index, 1);
            }
            
            // 서버 작업 버튼 활성화
            updateBackupActionButtons(serverName, false);
            
            // 실패 알림
            addSystemNotification('error', '백업 실패', `서버 ${serverName} 백업이 실패했습니다.`);
          } else if (res.state === 'PROGRESS') {
            console.log(`[instances.js] 백업 태스크 진행 중: ${res.progress}% - ${res.message}`);
            // 진행 상태는 로그만 출력 (UI 업데이트는 SSE로 처리)
          }
        },
        error: function(xhr) {
          console.error(`[instances.js] 백업 태스크 상태 조회 실패:`, xhr);
        }
      });
    }, 5000); // 5초마다 확인
    
    // 폴링 인터벌 저장
    backupPollingIntervals[serverName] = pollInterval;
    console.log(`[instances.js] 백업 태스크 폴링 인터벌 저장: ${serverName}`, pollInterval);
  }
  
  // 백업 생성 실행
  window.createServerBackup = function() {
    const serverName = $('#backup-server-name').val();
    const description = $('#backup-description').val();
    const compress = $('#backup-compress').val();
    const storage = $('#backup-storage').val();
    const mode = $('#backup-mode').val();
    
    console.log(`[instances.js] 백업 생성 시작: ${serverName}`, { description, compress, storage, mode });
    
    // 이미 백업 중인지 확인
    if (isServerBackingUp(serverName)) {
      console.log(`[instances.js] 이미 백업 중인 서버: ${serverName}`);
      alert(`서버 ${serverName}은(는) 이미 백업 중입니다.`);
      return;
    }
    
    const backupConfig = {
      description: description,
      compress: compress,
      storage: storage,
      mode: mode
    };
    
    console.log(`[instances.js] 백업 API 호출: /api/server/backup/${serverName}`, backupConfig);
    
    $.ajax({
      url: `/api/server/backup/${serverName}`,
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify(backupConfig),
      success: function(res) {
        console.log(`[instances.js] 백업 API 응답:`, res);
        
        if (res.success) {
          console.log(`[instances.js] 백업 생성 성공: ${serverName}, task_id: ${res.task_id}`);
          $('#backup-modal').modal('hide');
          
          // 백업 시작 알림
          addSystemNotification('info', '백업 시작', `서버 ${serverName} 백업이 시작되었습니다.`);
          
          // SSE를 통한 실시간 알림 수신 (폴링 불필요)
          console.log(`[instances.js] SSE를 통한 백업 알림 수신 대기: ${serverName}, task_id: ${res.task_id}`);
          
          // 백업 중인 서버 목록에 추가
          if (window.backingUpServers.indexOf(serverName) === -1) {
            window.backingUpServers.push(serverName);
          }
          
          // 서버 작업 버튼 비활성화
          updateBackupActionButtons(serverName, true);
          
          // 백업 목록 새로고침 (있다면)
          if (typeof loadBackupList === 'function') {
            console.log(`[instances.js] 백업 목록 새로고침 호출`);
            loadBackupList(serverName);
          }
        } else {
          console.log(`[instances.js] 백업 생성 실패:`, res.message || res.error);
          // 스냅샷 기능이 지원되지 않는 경우 특별 처리
          if (res.message && res.message.includes('스냅샷 기능이 지원되지 않습니다')) {
            alert(`⚠️ 백업 기능 제한\n\n${res.message}\n\n이 VM에서는 스냅샷 기반 백업이 지원되지 않습니다. Proxmox 관리자에게 문의하세요.`);
          } else {
            alert(`백업 생성 실패: ${res.message || res.error}`);
          }
        }
      },
      error: function(xhr) {
        console.error('[instances.js] 백업 생성 API 오류:', xhr);
        console.error('[instances.js] 응답 텍스트:', xhr.responseText);
        
        if (xhr.status === 400 && xhr.responseJSON && xhr.responseJSON.error && 
            xhr.responseJSON.error.includes('이미 백업 중입니다')) {
          alert(xhr.responseJSON.error);
        } else {
          alert('백업 생성에 실패했습니다.');
        }
      }
    });
  };
  
  // 백업 목록 보기
  window.viewServerBackups = function(serverName) {
    console.log(`[instances.js] 백업 목록 보기: ${serverName}`);
    
    $.ajax({
      url: `/api/server/backups/${serverName}`,
      method: 'GET',
      success: function(res) {
        if (res.success) {
          const backupData = res.backups;
          
          // 백업 목록 표시
          let backupListHtml = '';
          if (backupData.backups.length === 0) {
            backupListHtml = '<tr><td colspan="5" class="text-center text-muted">백업이 없습니다.</td></tr>';
          } else {
            backupData.backups.forEach(function(backup) {
              const timestamp = backup.timestamp ? new Date(backup.timestamp).toLocaleString() : '알 수 없음';
              const sizeDisplay = backup.size_gb ? `${backup.size_gb} GB` : '알 수 없음';
              const fileName = backup.name ? backup.name.split('/').pop() : '알 수 없음';
              
              backupListHtml += `
                <tr>
                  <td><small>${fileName}</small><br><small class="text-muted">${backup.storage}</small></td>
                  <td>${backup.storage}</td>
                  <td>${timestamp}</td>
                  <td>${sizeDisplay}</td>
                  <td>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteBackup('${serverName}', '${backup.name}')" title="백업 삭제">
                      <i class="fas fa-trash"></i>
                    </button>
                  </td>
                </tr>
              `;
            });
          }
          
          $('#backup-list-modal .modal-title').text(`${serverName} - 백업 목록`);
          $('#backup-list-tbody').html(backupListHtml);
          $('#backup-list-modal').modal('show');
        } else {
          alert(`백업 목록 조회 실패: ${res.message || res.error}`);
        }
      },
      error: function(xhr) {
        console.error('[instances.js] 백업 목록 조회 실패:', xhr);
        alert('백업 목록을 불러올 수 없습니다.');
      }
    });
  };
  
  // 서버 목록 불러오기 (리스트 뷰 전용)
  window.loadActiveServers = function() {
    console.log('[instances.js] loadActiveServers 호출');
    
    // 중복 호출 방지
    if (window.loadActiveServers.isLoading) {
      console.log('[instances.js] 이미 로딩 중입니다.');
      return;
    }
    window.loadActiveServers.isLoading = true;
    
    // 방화벽 그룹 목록을 먼저 가져오기
    $.get('/api/firewall/groups', function(fwData) {
      console.log('[instances.js] 방화벽 그룹 API 응답:', fwData);
      const firewallGroups = fwData.groups || [];
      console.log('[instances.js] 처리된 방화벽 그룹:', firewallGroups);
      
      $.ajax({
        url: '/api/all_server_status',
        method: 'GET',
        cache: false,
        headers: {
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache'
        }
      }).done(function(res) {
        console.log('[instances.js] /all_server_status 응답:', res);
        console.log('[instances.js] 서버 개수:', Object.keys(res.servers || {}).length);
        
        // 서버 개수 업데이트
        const serverCount = Object.keys(res.servers || {}).length;
        $('#server-count').text(`${serverCount}개`);
        
        // 서버 데이터 저장 (검색/필터링용)
        window.serversData = res.servers || {};
        window.firewallGroups = firewallGroups;
        
        if (serverCount === 0) {
          showEmptyState();
          window.loadActiveServers.isLoading = false;
          return;
        }
        
        // 리스트 뷰로 렌더링
        console.log('[instances.js] 리스트 뷰 렌더링');
        $('#servers-grid').hide();
        $('#servers-table-container').show();
        renderTableView(res.servers, firewallGroups);
        
        console.log('[instances.js] 서버 목록 로드 완료');
        
        // 백업 중인 서버 상태 확인
        checkAllBackupStatus();
        
        // 인스턴스 페이지에서는 자동 폴링 하지 않음
        // 사용자가 작업을 수행할 때만 상태 업데이트
        console.log('[instances.js] 자동 폴링 비활성화 - 작업 시에만 상태 업데이트');
        
        // 중복 호출 방지 해제
        window.loadActiveServers.isLoading = false;
      }).fail(function(xhr) {
        console.error('[instances.js] /all_server_status 실패:', xhr);
        showErrorState();
        window.loadActiveServers.isLoading = false;
      });
    }).fail(function(xhr) {
      console.error('[instances.js] 방화벽 그룹 목록 조회 실패:', xhr);
      window.loadActiveServers.isLoading = false;
    });
  };
  
  // 현재 뷰 타입 가져오기 (리스트 뷰 전용)
  function getCurrentViewType() {
    return 'table'; // 항상 테이블 뷰
  }
  
  // 빈 상태 표시
  function showEmptyState() {
    const emptyHtml = `
      <div class="empty-state">
        <div class="empty-icon">
          <i class="fas fa-server"></i>
        </div>
        <h3>서버가 없습니다</h3>
        <p>새로운 서버를 생성하여 시작해보세요.</p>
        <button class="btn-modern btn-primary" onclick="switchToCreateTab()">
          <i class="fas fa-plus"></i>
          <span>서버 생성</span>
        </button>
      </div>
    `;
    
    $('#servers-grid').html(emptyHtml);
    $('#servers-table tbody').html('');
  }
  
  // 에러 상태 표시
  function showErrorState() {
    const errorHtml = `
      <div class="empty-state">
        <div class="empty-icon">
          <i class="fas fa-exclamation-triangle"></i>
        </div>
        <h3>서버 정보를 불러오지 못했습니다</h3>
        <p>네트워크 연결을 확인하고 다시 시도해주세요.</p>
        <button class="btn-modern btn-refresh" onclick="loadActiveServers()">
          <i class="fas fa-sync-alt"></i>
          <span>다시 시도</span>
        </button>
      </div>
    `;
    
    $('#servers-grid').html(errorHtml);
    $('#servers-table tbody').html('<tr><td colspan="9" class="text-center text-danger">서버 정보를 불러오지 못했습니다.</td></tr>');
  }
  

  
  // 테이블 뷰 렌더링
  function renderTableView(servers, firewallGroups) {
    // 현재 선택된 서버들 저장
    const selectedServers = getSelectedServerNames();
    console.log('[instances.js] 현재 선택된 서버들:', selectedServers);
    
    let html = '';
    for (const [name, s] of Object.entries(servers)) {
      // 상태 배지
      let statusBadge = '';
      switch(s.status) {
        case 'running': 
          statusBadge = '<span class="status-badge status-success">실행 중</span>';
          break;
        case 'stopped':
          statusBadge = '<span class="status-badge status-stopped">중지됨</span>';
          break;
        case 'paused':
          statusBadge = '<span class="status-badge status-warning">일시정지</span>';
          break;
        default:
          statusBadge = '<span class="status-badge status-unknown">' + s.status + '</span>';
      }
      
      // 역할 상태 표시 (개선된 버전)
      const roleDisplay = (() => {
        if (!s.role || s.role === '' || s.role === null || s.role === undefined) {
          return '<span class="text-muted">(설정 안 함)</span>';
      } else {
          return window.dashboardRoleMap[s.role] || s.role;
      }
      })();   
      
      // Security Group 상태 표시
      const securityGroupDisplay = s.firewall_group ? s.firewall_group : '<span class="text-muted">(설정 안 함)</span>';
      
      // IP 주소 표시
      const ipAddresses = (s.ip_addresses && s.ip_addresses.length > 0) 
        ? s.ip_addresses.join(', ') 
        : '미할당';
      
      // 메모리 포맷팅 (GB)
      const memoryGB = ((s.memory || 0) / 1024 / 1024 / 1024).toFixed(1);
      
      // 체크박스 상태 복원
      const isChecked = selectedServers.includes(s.name) ? 'checked' : '';
      
      const serverRow = `
        <tr class="server-row" data-server="${s.name}" data-status="${s.status}" data-role="${s.role || ''}" data-memory="${s.memory || 0}" data-cpu="${s.vm_cpu || 0}">
          <td class="select-column">
            <input type="checkbox" class="form-check-input server-checkbox" value="${s.name}" ${isChecked}>
          </td>
          <td class="server-name-cell" style="cursor: pointer;">
            <div class="d-flex align-items-center">
              <i class="fas fa-chevron-right expand-icon me-2" style="transition: transform 0.2s;"></i>
              <strong>${s.name}</strong>
            </div>
          </td>
          <td>${statusBadge}</td>
          <td class="role-column">
            <div class="role-display">
              <i class="fas fa-tag me-1 text-muted"></i>
              ${roleDisplay}
            </div>
          </td>
          <td>${s.vm_cpu || 0}코어</td>
          <td>${memoryGB}GB</td>
          <td>${ipAddresses}</td>
          <td class="security-column">
            <div class="security-group-display">
              <i class="fas fa-shield-alt me-1 text-muted"></i>
              ${securityGroupDisplay}
            </div>
          </td>
          <td>
            <div class="table-actions">
              <button class="btn btn-success btn-sm start-btn" title="시작" ${s.status === 'running' ? 'disabled' : ''}>
                <i class="fas fa-play"></i>
              </button>
              <button class="btn btn-warning btn-sm stop-btn" title="중지" ${s.status === 'stopped' ? 'disabled' : ''}>
                <i class="fas fa-pause"></i>
              </button>
              <button class="btn btn-info btn-sm reboot-btn" title="재시작" ${s.status === 'stopped' ? 'disabled' : ''}>
                <i class="fas fa-redo"></i>
              </button>
              <button class="btn btn-danger btn-sm delete-btn" title="삭제">
                <i class="fas fa-trash"></i>
              </button>
            </div>
          </td>
        </tr>
        <tr class="server-detail-row" data-server="${s.name}" style="display: none;">
          <td colspan="9">
            <div class="server-detail-content p-3 bg-light border-top">
              <div class="row">
                <div class="col-md-6">
                  <h6 class="mb-3"><i class="fas fa-info-circle text-primary"></i> 서버 상세 정보</h6>
                  <div class="row mb-2">
                    <div class="col-4"><strong>VM ID:</strong></div>
                    <div class="col-8">${s.vmid || 'N/A'}</div>
                  </div>
                  <div class="row mb-2">
                    <div class="col-4"><strong>노드:</strong></div>
                    <div class="col-8">${s.node || 'N/A'}</div>
                  </div>
                  <div class="row mb-2">
                    <div class="col-4"><strong>CPU 할당:</strong></div>
                    <div class="col-8">${s.vm_cpu || s.cpu || 0} 코어</div>
                  </div>
                  <div class="row mb-2">
                    <div class="col-4"><strong>메모리 할당:</strong></div>
                    <div class="col-8">${Math.round((s.maxmem || s.memory || 0) / (1024 * 1024 * 1024))} GB</div>
                  </div>
                  <div class="row mb-2">
                    <div class="col-4"><strong>디스크 할당:</strong></div>
                    <div class="col-8">
                      ${s.total_disk_gb || Math.round((s.maxdisk || s.disk || 0) / (1024 * 1024 * 1024))} GB (총합)
                      ${s.disks && s.disks.length > 0 ? 
                        '<br><small class="text-muted">' + 
                        s.disks.map(disk => `${disk.device}: ${disk.size_gb}GB (${disk.storage})`).join(', ') + 
                        '</small>' : 
                        ''
                      }
                    </div>
                  </div>
                </div>
                <div class="col-md-6">
                  <h6 class="mb-3"><i class="fas fa-network-wired text-success"></i> 네트워크 정보</h6>
                  <div class="row mb-2">
                    <div class="col-4"><strong>IP 주소:</strong></div>
                    <div class="col-8">${ipAddresses}</div>
                  </div>
                  <div class="row mb-2">
                    <div class="col-4"><strong>방화벽 그룹:</strong></div>
                    <div class="col-8">${s.firewall_group || '미설정'}</div>
                  </div>
                  <div class="row mb-2">
                    <div class="col-4"><strong>역할:</strong></div>
                    <div class="col-8">${s.role ? window.dashboardRoleMap[s.role] || s.role : '미설정'}</div>
                  </div>
                  <div class="row mb-2">
                    <div class="col-4"><strong>상태:</strong></div>
                    <div class="col-8">${s.status}</div>
                  </div>
                </div>
              </div>
              <div class="mt-3">
                <button class="btn btn-outline-primary btn-sm me-2" onclick="openServerConfig('${s.name}')">
                  <i class="fas fa-cog"></i> 서버 설정
                </button>
                <button class="btn btn-outline-info btn-sm me-2" onclick="viewServerLogs('${s.name}')">
                  <i class="fas fa-file-alt"></i> 로그 보기
                </button>
                <button class="btn btn-outline-warning btn-sm" onclick="backupServer('${s.name}')">
                  <i class="fas fa-download"></i> 백업
                </button>
              </div>
            </div>
          </td>
        </tr>
      `;
      
      html += serverRow;
    }
    
    $('#servers-table tbody').html(html);
    
    // 전체 선택 체크박스 상태 복원
    const totalCheckboxes = $('.server-checkbox').length;
    const checkedCheckboxes = $('.server-checkbox:checked').length;
    
    if (checkedCheckboxes === 0) {
      $('#select-all-servers').prop('indeterminate', false).prop('checked', false);
    } else if (checkedCheckboxes === totalCheckboxes) {
      $('#select-all-servers').prop('indeterminate', false).prop('checked', true);
    } else {
      $('#select-all-servers').prop('indeterminate', true);
    }
    
    // 일괄 작업 도구모음 상태 업데이트
    updateBulkActionsToolbar();
    
    // 서버 이름 클릭 이벤트 바인딩
    $('.server-name-cell').off('click').on('click', function(e) {
      e.stopPropagation();
      const serverName = $(this).closest('tr').data('server');
      const detailRow = $(`.server-detail-row[data-server="${serverName}"]`);
      const expandIcon = $(this).find('.expand-icon');
      
      if (detailRow.is(':visible')) {
        // 상세 정보 접기
        detailRow.slideUp(200);
        expandIcon.css('transform', 'rotate(0deg)');
      } else {
        // 다른 모든 상세 정보 접기
        $('.server-detail-row').slideUp(200);
        $('.expand-icon').css('transform', 'rotate(0deg)');
        
        // 현재 서버 상세 정보 펼치기
        detailRow.slideDown(200);
        expandIcon.css('transform', 'rotate(90deg)');
      }
    });
  }
  
  // 중복 바인딩 방지: 기존 이벤트 제거
  $('#list-tab').off('shown.bs.tab');
  
  // 최초 진입 시 서버 목록 탭이 active면 한 번만 호출
  if ($('#list-tab').hasClass('active')) {
  loadActiveServers();
  }
  
  // 기존 바인딩 제거 후 바인딩
  $('#list-tab').off('shown.bs.tab').on('shown.bs.tab', function() {
    console.log('[instances.js] list-tab shown');
    loadActiveServers();
  });

  // 작업 상태 폴링 제거: SSE만 사용
  // pollTaskStatus는 더 이상 사용하지 않지만, 기존 호출부를 안전하게 무시하기 위해 no-op으로 유지
  function pollTaskStatus() { /* SSE 전환으로 미사용 */ }


  // AJAX 전역 설정 - 세션 만료 처리
  $.ajaxSetup({
    statusCode: {
      401: function() {
        console.log('[instances.js] AJAX 401 오류 - 세션 만료');
        if (window.sessionManager) {
          window.sessionManager.handleSessionExpired();
        } else {
          window.location.href = '/auth/login';
        }
      }
    }
  });

  // 서버 생성 버튼 (단일/다중 모드 분기, 중복 바인딩 제거)
  $(document).off('click', '#create-server-btn').on('click', '#create-server-btn', async function(e) {
    // 중복 실행 방지
    if ($(this).data('processing')) return;
    $(this).data('processing', true);
    
    const mode = $('#server_mode').val();
    if (mode === 'multi') {
      // 다중 서버 로직 (기존 다중 서버 코드)
      e.preventDefault();
      // 입력값 수집
      const count = parseInt($('#multi-server-count').val());
      const baseName = $('input[name="name_basic"]').val();
      const selectedRole = ''; // 역할 선택 제거됨
      const selectedOS = $('#os-select').val();
      const cpu = parseInt($('input[name="cpu_basic"]').val());
      const memory = parseInt($('input[name="memory_basic"]').val());
      // 디스크/네트워크 정보 복제
      const disks = $('#disk-container-basic').find('.disk-item').map(function() {
        return {
          size: parseInt($(this).find('.disk-size').val()),
          interface: $(this).find('.disk-interface').val(),
          datastore_id: $(this).find('.disk-datastore').val()
        };
      }).get();
      const networks = $('#network-container-basic').find('.network-item').map(function() {
        return {
          bridge: $(this).find('.network-bridge').val(),
          ip: $(this).find('.network-ip').val(),
          subnet: $(this).find('.network-subnet').val(),
          gateway: $(this).find('.network-gateway').val()
        };
      }).get();
      if (!selectedOS) { 
        alertModal('OS를 선택해주세요.'); 
        return false; 
      }
      if (!baseName || baseName.trim() === '') { 
        alertModal('서버 이름을 입력해주세요.'); 
        return false; 
      }
      if (!count || count < 2) { 
        alertModal('서버 개수는 2 이상이어야 합니다.'); 
        return false; 
      }
      // 네트워크 입력값 검증 (IP, 서브넷, 게이트웨이 모두 필수)
      let hasError = false;
      networks.forEach(function(n, idx) {
        if (!n.ip || !n.subnet || !n.gateway) {
          alertModal(`네트워크 카드 #${idx+1}의 IP, 서브넷, 게이트웨이를 모두 입력해주세요.`);
          hasError = true;
        }
      });
      if (hasError) return false;
      // 서버별 정보 생성 (IP 자동 증가, 네트워크 여러 개 지원)
      function ipAdd(ip, add) {
        const parts = ip.split('.').map(Number);
        parts[3] += add;
        if (parts[3] > 254) parts[3] = 254;
        return parts.join('.')
      }
      const serverList = [];
      for (let i = 0; i < count; i++) {
        // 네트워크 여러 개 지원: 각 네트워크의 ip만 i만큼 증가
        const nets = networks.map((net, ni) => {
          const newNet = {...net};
          if (i > 0 && newNet.ip) {
            newNet.ip = ipAdd(net.ip, i);
          }
          return newNet;
        });
        serverList.push({
          name: `${baseName}-${i+1}`,
          role: selectedRole,
          os: selectedOS,
          cpu: cpu,
          memory: memory,
          disks: JSON.parse(JSON.stringify(disks)),
          networks: nets
        });
      }
      // 역할 select 옵션 생성
      let roleOptions = '<option value="">(선택 안 함)</option>';
      for (const [k, v] of Object.entries(window.dashboardRoleMap)) {
        roleOptions += `<option value="${k}">${v}</option>`;
      }
      // 서버 생성 폼을 다중 서버 요약 화면으로 교체
      $('#create-server-form').html('<div id="multiServerSummarySection"></div>');
      
      // 요약 섹션 로드
      $.get('/api/instances/multi-server-summary', function(html) {
        console.log('다중서버 요약 템플릿 로드 성공:', html.substring(0, 100) + '...');
        $('#multiServerSummarySection').html(html);
        
        // 테이블 내용 동적 생성
        let tableRows = '';
        serverList.forEach((s, sidx) => {
          s.networks.forEach((net, nidx) => {
            tableRows += `
              <tr data-sidx="${sidx}" data-nidx="${nidx}">
                ${nidx === 0 ? `
                  <td rowspan="${s.networks.length}">
                    <input type="text" class="form-control form-control-sm summary-name" value="${s.name}" placeholder="서버명">
                  </td>
                  <td rowspan="${s.networks.length}">${s.os}</td>
                  <td rowspan="${s.networks.length}">
                    <input type="number" class="form-control form-control-sm summary-cpu" value="${s.cpu}" min="1" max="32" placeholder="코어">
                  </td>
                  <td rowspan="${s.networks.length}">
                    <input type="number" class="form-control form-control-sm summary-memory" value="${s.memory}" min="1" max="131072" placeholder="MB">
                  </td>
                  <td rowspan="${s.networks.length}">
                    <div class="disk-inputs">
                      ${s.disks.map((d, didx) => `
                        <div class="mb-1">
                          <input type="number" class="form-control form-control-sm summary-disk-size" 
                                 data-disk-idx="${didx}" value="${d.size}" min="1" max="1000" placeholder="GB">
                          <small class="text-muted">${d.interface}/${d.datastore_id}</small>
                        </div>
                      `).join('')}
                    </div>
                  </td>
                  <td rowspan="${s.networks.length}">
                    <select class="form-select form-select-sm summary-role">${roleOptions.replace(`value=\"${s.role}\"`, `value=\"${s.role}\" selected`)}</select>
                  </td>
                ` : ''}
                <td><input type="text" class="form-control form-control-sm summary-bridge" value="${net.bridge}"></td>
                <td><input type="text" class="form-control form-control-sm summary-ip" value="${net.ip}"></td>
                <td><input type="text" class="form-control form-control-sm summary-subnet" value="${net.subnet}"></td>
                <td><input type="text" class="form-control form-control-sm summary-gateway" value="${net.gateway}"></td>
              </tr>
            `;
          });
        });
        
        $('#multi-server-summary-tbody').html(tableRows);
        
        // 페이지를 요약 섹션으로 스크롤
        $('#multiServerSummarySection')[0].scrollIntoView({ behavior: 'smooth' });
      }).fail(function(xhr, status, error) {
        console.error('다중서버 요약 템플릿 로드 실패:', error);
        console.error('상태:', status);
        console.error('응답:', xhr.responseText);
        alertModal('다중서버 요약 화면을 로드할 수 없습니다: ' + error);
      });
      // 서버 생성 버튼 클릭 시 - 중복 바인딩 방지
      $(document).off('click', '#multi-server-final-create').on('click', '#multi-server-final-create', function() {
        const $btn = $(this);
        const $section = $('#multiServerSummarySection');
        
        // 중복 실행 방지
        if ($btn.data('processing')) return;
        $btn.data('processing', true);
        
        // 버튼 비활성화로 중복 클릭 방지
        $btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin me-2"></i>생성 중...');
        
        // 수정된 값 반영
        $('#multiServerSummarySection tbody tr').each(function() {
          const sidx = $(this).data('sidx');
          const nidx = $(this).data('nidx');
          
          if (nidx === 0) {
            // 서버 기본 정보 반영
            serverList[sidx].name = $(this).find('.summary-name').val();
            serverList[sidx].cpu = parseInt($(this).find('.summary-cpu').val()) || 1;
            serverList[sidx].memory = parseInt($(this).find('.summary-memory').val()) || 1;
            serverList[sidx].role = $(this).find('.summary-role').val();
            
            // 디스크 크기 반영
            $(this).find('.summary-disk-size').each(function() {
              const diskIdx = $(this).data('disk-idx');
              const newSize = parseInt($(this).val()) || 1;
              if (serverList[sidx].disks[diskIdx]) {
                serverList[sidx].disks[diskIdx].size = newSize;
              }
            });
          }
          
          // 네트워크 정보 반영
          serverList[sidx].networks[nidx].bridge = $(this).find('.summary-bridge').val();
          serverList[sidx].networks[nidx].ip = $(this).find('.summary-ip').val();
          serverList[sidx].networks[nidx].subnet = $(this).find('.summary-subnet').val();
          serverList[sidx].networks[nidx].gateway = $(this).find('.summary-gateway').val();
        });
        
        // 유효성 검사
        const errors = [];
        serverList.forEach((s, idx) => {
          if (!s.name || s.name.trim() === '') {
            errors.push(`서버 ${idx + 1}: 서버명을 입력해주세요.`);
          }
          if (s.cpu < 1 || s.cpu > 32) {
            errors.push(`서버 ${s.name}: CPU는 1-32 코어 사이여야 합니다.`);
          }
          if (s.memory < 1 || s.memory > 131072) {
            errors.push(`서버 ${s.name}: 메모리는 1-131072 MB 사이여야 합니다.`);
          }
          s.disks.forEach((disk, diskIdx) => {
            if (disk.size < 1 || disk.size > 1000) {
              errors.push(`서버 ${s.name} 디스크 ${diskIdx + 1}: 디스크 크기는 1-1000 GB 사이여야 합니다.`);
            }
          });
        });
        
        if (errors.length > 0) {
          alertModal('입력 오류:\n' + errors.join('\n'));
          $btn.prop('disabled', false).html('<i class="fas fa-plus me-2"></i>서버 생성');
          $btn.data('processing', false);
          return;
        }
        
        // 서버 정보 배열 생성
        const servers = serverList.map(s => ({
          name: s.name,
          role: s.role,
          cpu: s.cpu,
          memory: s.memory,
          disks: s.disks,
          network_devices: s.networks.map(net => ({
            bridge: net.bridge,
            ip_address: net.ip,
            subnet: net.subnet,
            gateway: net.gateway
          })),
          template_vm_id: (function(){
            const osMap = { 'ubuntu': 9000, 'rocky': 8000, 'centos': 8001, 'debian': 9001 };
            return osMap[s.os] || 8000;
          })()
        }));
        
        // 한 번에 서버 정보 배열 전송
        $.ajax({
          url: '/api/create_servers_bulk',
          method: 'POST',
          contentType: 'application/json',
          data: JSON.stringify({servers}),
          success: function(res) {
            if (res.success && res.task_id) {
              addSystemNotification('success', '서버 생성', res.message);
              // 작업 상태 폴링 시작
              pollTaskStatus(res.task_id, 'create_servers_bulk', serverList.map(s => s.name).join(', '));
            } else {
              addSystemNotification('success', '서버 생성', '다중 서버 생성 요청 완료');
              // 서버 생성 폼 복원
              restoreServerForm();
              loadActiveServers();
            }
          },
          error: function(xhr) {
            addSystemNotification('error', '서버 생성', '다중 서버 생성 실패: ' + (xhr.responseJSON?.error || xhr.statusText));
            // 서버 생성 폼 복원
            restoreServerForm();
            loadActiveServers();
          },
          complete: function() {
            // 버튼 상태 복원
            $btn.prop('disabled', false).html('서버 생성');
          }
        });
            });
      
      // 취소 버튼 클릭 시 서버 생성 폼으로 되돌리기
      $(document).off('click', '#multi-server-cancel').on('click', '#multi-server-cancel', function() {
        // 중복 실행 방지
        if ($(this).data('processing')) return;
        $(this).data('processing', true);
        
        // 서버 생성 폼 복원
        restoreServerForm();
        
        // 작업 완료 후 처리 상태 해제
        $(this).data('processing', false);
      });
      
      return; // 다중 서버 모드에서는 여기서 종료
    }
    
    // 단일 서버 로직 (기존 단일 서버 코드)
    const selectedRole = ''; // 역할 선택 제거됨
    const selectedOS = $('#os-select').val();
    if (!selectedOS) { 
      alertModal('OS를 선택해주세요.'); 
      return false; 
    }
    const name = $('input[name="name_basic"]').val();
    if (!name || name.trim() === '') { 
      alertModal('서버 이름을 입력해주세요.'); 
      return false; 
    }
    // IP 주소 검증
    let hasError = false;
    $('#network-container-basic').find('.network-ip').each(function() {
      const ip = $(this).val();
      if (!ip || ip.trim() === '') {
        alertModal('IP 주소를 입력해주세요.');
        hasError = true;
        return false;
      }
    });
    if (hasError) return false;
    // 서버 생성
    createBasicServer(name, selectedOS, selectedRole);
  });

// 서버 생성 폼 복원 함수
function restoreServerForm() {
  // 서버 생성 폼 다시 로드
  $.get('/instances/content', function(html) {
    // create-server-form 부분만 추출
    const formHtml = $(html).find('#create-server-form').html();
    $('#create-server-form').html(formHtml);
    
    // 폼 초기화
    initializeServerForm();
  });
}

// 서버 생성 폼 초기화 함수
function initializeServerForm() {
  // 다중 서버 옵션 숨기기
  $('#multi-server-options').hide();
  
  // 서버 모드 단일로 설정
  $('#server_mode').val('single');
  $('.mode-card').removeClass('active');
  $('.mode-card[data-mode="single"]').addClass('active');
  
  // 폼 필드 초기화
  (function safeResetForm() {
    const $form = $('#create-server-form');
    if ($form.length) {
      const el = $form.get(0);
      if (el && typeof el.reset === 'function') {
        el.reset();
      }
    }
  })();
  
  // 디스크/네트워크 기본값 설정
  if ($('.disk-size').length) $('.disk-size').val('20');
  if ($('.disk-interface').length) $('.disk-interface').val('scsi0');
  if ($('.disk-datastore').length) $('.disk-datastore').val('local-lvm');
  if ($('.network-subnet').length) $('.network-subnet').val('24');
  
  // 첫 번째 디스크/네트워크의 삭제 버튼 비활성화
  if ($('.remove-disk-btn:first').length) $('.remove-disk-btn:first').prop('disabled', true);
  if ($('.remove-network-btn:first').length) $('.remove-network-btn:first').prop('disabled', true);
}

  // 기본 서버 생성 함수 (기존 로직 복원)
  function createBasicServer(name, selectedOS, selectedRole) {
    console.log('[instances.js] createBasicServer 호출', name, selectedOS, selectedRole);
    const btn = $('#create-server-btn');
    const originalText = btn.html();
    
    // 중복 실행 방지 해제
    btn.data('processing', false);
    
    btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin me-2"></i>생성 중...');
    $('#creation-status').show();
    $('#status-message').html('서버 생성 진행 중입니다. 잠시만 기다려주세요...');
    const cpu = parseInt($('input[name="cpu_basic"]').val());
    const memory = parseInt($('input[name="memory_basic"]').val());
    const disks = $('#disk-container-basic').find('.disk-item').map(function() {
      return {
        size: parseInt($(this).find('.disk-size').val()),
        interface: $(this).find('.disk-interface').val(),
        datastore_id: $(this).find('.disk-datastore').val()
      };
    }).get();
    const networks = $('#network-container-basic').find('.network-item').map(function() {
      return {
        bridge: $(this).find('.network-bridge').val(),
        ip_address: $(this).find('.network-ip').val(), // 순수 IP만
        subnet: $(this).find('.network-subnet').val(),
        gateway: $(this).find('.network-gateway').val()
      };
    }).get();
    const osTemplateMapping = {
      'ubuntu': 9000,
      'rocky': 8000,
      'centos': 8001,
      'debian': 9001
    };
    const template_vm_id = osTemplateMapping[selectedOS] || 8000;
    const data = {
      name: name,
      role: selectedRole,
      cpu: cpu,
      memory: memory,
      disk: disks[0]?.size || 20,  // disk 필드 추가
      disks: disks,
      network_devices: networks,
      template_vm_id: template_vm_id
    };
    $('#status-message').html('서버 생성 진행 중입니다. 잠시만 기다려주세요...');
    $.ajax({
      url: '/api/servers/async',
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify(data),
      beforeSend: function() {
        console.log('[instances.js] /add_server 요청 전', data);
      },
      success: function(res) {
        console.log('[instances.js] /add_server 성공', res);
        if (res.task_id) {
          pollTaskStatus(res.task_id, '서버 생성', name);
        }
        $('#status-message').html('서버 생성 요청이 접수되었습니다. 진행 상황은 알림에서 확인하세요.');
        setTimeout(function() {
          $('#creation-status').hide();
          btn.prop('disabled', false).html(originalText);
        }, 2000);
      },
      error: function(xhr) {
        console.error('[instances.js] /add_server 실패', xhr);
        $('#status-message').html('서버 생성 실패');
        addSystemNotification('error', '서버 생성', '서버 생성 요청 실패: ' + (xhr.responseJSON?.stderr || xhr.responseJSON?.error || xhr.statusText));
        setTimeout(function() {
          $('#creation-status').hide();
          btn.prop('disabled', false).html(originalText);
        }, 2000);
      }
    });
  }





  // Security Group 적용
  $(document).off('click', '.server-security-group-apply').on('click', '.server-security-group-apply', function() {
    console.log('[instances.js] .server-security-group-apply 클릭');
    const btn = $(this);
    const tr = btn.closest('tr');
    const server = tr.data('server');
    const securityGroup = tr.find('.server-security-group-select').val();
    
    if (!securityGroup) {
      addSystemNotification('error', 'Security Group 적용', 'Security Group을 선택해주세요.');
      return;
    }
    
    // 시작 알림 추가
    addSystemNotification('info', 'Security Group 적용', `${server} 서버에 ${securityGroup} Security Group을 적용하는 중...`);
    
    btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> <span>적용 중...</span>');
    $.ajax({
      url: `/api/apply_security_group/${server}`,
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({ security_group: securityGroup }),
      success: function(res) {
      console.log('[instances.js] /api/apply_security_group 성공', res);
      btn.prop('disabled', false).html('<i class="fas fa-check"></i> <span>적용</span>');
      loadActiveServers();
      addSystemNotification('success', 'Security Group 적용', `${server} 서버에 ${securityGroup} Security Group이 성공적으로 적용되었습니다.`);
      },
      error: function(xhr) {
      console.error('[instances.js] /api/apply_security_group 실패', xhr);
      btn.prop('disabled', false).html('<i class="fas fa-check"></i> <span>적용</span>');
      
      let errorMsg = '알 수 없는 오류';
      if (xhr.status === 403) {
        errorMsg = '권한이 없습니다. Security Group 할당 권한이 필요합니다.';
      } else if (xhr.responseJSON?.error) {
        errorMsg = xhr.responseJSON.error;
      }
      
      addSystemNotification('error', 'Security Group 적용', `${server} 서버 Security Group 적용 실패: ${errorMsg}`);
      }
    });
  });



  // 서버 시작
  $(document).off('click', '.start-btn').on('click', '.start-btn', async function() {
    console.log('[instances.js] .start-btn 클릭');
    const name = $(this).closest('tr').data('server');
    const btn = $(this);
    const originalText = btn.html();
    const ok = await confirmModal(`${name} 서버를 시작하시겠습니까?`);
    if (!ok) return;
    btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin me-1"></i>시작 중...');
    $.post('/api/servers/' + name + '/start', function(res) {
      console.log('[instances.js] /api/servers/' + name + '/start 성공', res);
      if (res.success) {
        // 시작 알림을 즉시 띄우지 않음. 완료 알림은 SSE로 수신.
        console.log(`[instances.js] 서버 시작 요청 전송 완료: ${name}`);
      } else {
        // 오류 알림은 SSE로 처리됨
      btn.prop('disabled', false).html(originalText);
      }
    }).fail(function(xhr){
      console.error('[instances.js] /api/servers/' + name + '/start 실패', xhr);
      btn.prop('disabled', false).html(originalText);
      
      let errorMsg = xhr.statusText;
      if (xhr.status === 403) {
        errorMsg = '권한이 없습니다. 서버 시작 권한이 필요합니다.';
      } else if (xhr.responseJSON?.error) {
        errorMsg = xhr.responseJSON.error;
      }
      
      // 오류 알림은 SSE로 처리됨
    });
  });

  // 서버 중지
  $(document).off('click', '.stop-btn').on('click', '.stop-btn', async function() {
    console.log('[instances.js] .stop-btn 클릭');
    const name = $(this).closest('tr').data('server');
    const btn = $(this);
    const originalText = btn.html();
    const ok = await confirmModal(`${name} 서버를 중지하시겠습니까?`);
    if (!ok) return;
    btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin me-1"></i>중지 중...');
    $.post('/api/servers/' + name + '/stop', function(res) {
      console.log('[instances.js] /api/servers/' + name + '/stop 성공', res);
      if (res.success) {
        // 시작 알림을 즉시 띄우지 않음. 완료 알림은 SSE로 수신.
        console.log(`[instances.js] 서버 중지 요청 전송 완료: ${name}`);
      } else {
        // 오류 알림은 SSE로 처리됨
      btn.prop('disabled', false).html(originalText);
      }
    }).fail(function(xhr){
      console.error('[instances.js] /api/servers/' + name + '/stop 실패', xhr);
      btn.prop('disabled', false).html(originalText);
      
      let errorMsg = xhr.statusText;
      if (xhr.status === 403) {
        errorMsg = '권한이 없습니다. 서버 중지 권한이 필요합니다.';
      } else if (xhr.responseJSON?.error) {
        errorMsg = xhr.responseJSON.error;
      }
      
      // 오류 알림은 SSE로 처리됨
    });
  });

  // 서버 리부팅
  $(document).off('click', '.reboot-btn').on('click', '.reboot-btn', async function() {
    console.log('[instances.js] .reboot-btn 클릭');
    const name = $(this).closest('tr').data('server');
    const btn = $(this);
    const originalText = btn.html();
    const ok = await confirmModal(`${name} 서버를 리부팅하시겠습니까?`);
    if (!ok) return;
    btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin me-1"></i>리부팅 중...');
    $.post('/api/servers/' + name + '/reboot', function(res) {
      console.log('[instances.js] /api/servers/' + name + '/reboot 성공', res);
      if (res.success) {
        // 시작 알림을 즉시 띄우지 않음. 완료 알림은 SSE로 수신.
        console.log(`[instances.js] 서버 재시작 요청 전송 완료: ${name}`);
      } else {
        // 오류 알림은 SSE로 처리됨
      btn.prop('disabled', false).html(originalText);
      }
    }).fail(function(xhr){
      console.error('[instances.js] /api/servers/' + name + '/reboot 실패', xhr);
      btn.prop('disabled', false).html(originalText);
      
      let errorMsg = xhr.statusText;
      if (xhr.status === 403) {
        errorMsg = '권한이 없습니다. 서버 재시작 권한이 필요합니다.';
      } else if (xhr.responseJSON?.error) {
        errorMsg = xhr.responseJSON.error;
      }
      
      // 오류 알림은 SSE로 처리됨
    });
  });

  // 서버 삭제 버튼 안전하게 중복 바인딩 없이 처리
  $(document).off('click', '.delete-btn').on('click', '.delete-btn', async function() {
    console.log('[instances.js] .delete-btn 클릭');
    const name = $(this).closest('tr').data('server');
    const btn = $(this);
    const originalText = btn.html();
    // confirm 없이 바로 삭제 진행
    btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin me-1"></i>삭제 중...');
    btn.closest('tr').addClass('table-warning');
    $.post('/api/servers/' + name + '/delete', function(res) {
      console.log('[instances.js] /api/servers/' + name + '/delete 성공', res);
      if (res.success) {
        addSystemNotification('info', '서버 삭제', `${name} 서버 삭제 작업이 시작되었습니다.`);
        // Task 폴링 시작
      if (res.task_id) {
          pollTaskStatus(res.task_id, 'server_delete', name);
        }
      } else {
        // 오류 알림은 SSE로 처리됨
        btn.prop('disabled', false).html(originalText);
        btn.closest('tr').removeClass('table-warning');
      }
    }).fail(function(xhr){
      console.error('[instances.js] /api/servers/' + name + '/delete 실패', xhr);
      btn.prop('disabled', false).html(originalText);
      btn.closest('tr').removeClass('table-warning');
      
      let errorMsg = xhr.statusText;
      if (xhr.status === 403) {
        errorMsg = '권한이 없습니다. 서버 삭제 권한이 필요합니다.';
      } else if (xhr.responseJSON?.error) {
        errorMsg = xhr.responseJSON.error;
      }
      
      // 오류 알림은 SSE로 처리됨
    });
  });

  // 서버명 클릭 시 상세 모달 표시
  $(document).on('click', '.server-detail-link', function(e) {
    e.preventDefault();
    const name = $(this).data('server');
    // 상세 모달 로드 및 이벤트 연결 (기존 index.html 구조 복원)
    // ... 상세 모달 코드 ...
  });

  // 상세 모달 내 역할 적용/삭제
  $(document).off('click', '.server-detail-role-apply').on('click', '.server-detail-role-apply', function() { /* ... */ });
  $(document).off('click', '.server-detail-role-remove').on('click', '.server-detail-role-remove', function() { /* ... */ });

  // 디스크 삭제 버튼 클릭 시 (중복 바인딩 방지)
  $(document).off('click', '.remove-disk-btn').on('click', '.remove-disk-btn', function() {
    const diskItem = $(this).closest('.disk-item');
    const container = diskItem.closest('.disk-container');
    diskItem.remove();
    // 마지막 하나 남았을 때 삭제 버튼 비활성화
    if (container.find('.disk-item').length === 1) {
      container.find('.disk-item:first .btn-outline-danger').prop('disabled', true);
    }
  });

  // 새로고침 버튼 클릭 시 서버 목록 갱신
  $(document).off('click', '.refresh-btn').on('click', '.refresh-btn', function() {
    console.log('[instances.js] .refresh-btn 클릭');
    
    // 일괄 작업 중에는 강제 새로고침 허용
    if (isBulkOperationInProgress) {
      console.log('[instances.js] 일괄 작업 중 강제 새로고침 실행');
      isBulkOperationInProgress = false; // 플래그 해제
      updateRefreshButtonState();
    }
    
    loadActiveServers();
  });

  // 뷰 전환 버튼 클릭 이벤트
  $(document).off('click', '.btn-view').on('click', '.btn-view', function() {
    const viewType = $(this).data('view');
    console.log('[instances.js] 뷰 전환 버튼 클릭:', viewType);
    
    // 활성 버튼 변경
    $('.btn-view').removeClass('active');
    $(this).addClass('active');
    
    console.log('[instances.js] 뷰 컨테이너 전환 시작');
    
    // 뷰 컨테이너 전환
    if (viewType === 'table') {
      console.log('[instances.js] 테이블 뷰로 전환');
      $('#servers-grid').hide();
      $('#servers-table-container').show();
      // 테이블 뷰로 다시 렌더링
      if (window.serversData) {
        renderTableView(window.serversData, window.firewallGroups || []);
      }
    } else {
      console.log('[instances.js] 카드 뷰로 전환');
      $('#servers-table-container').hide();
      $('#servers-grid').show();
      // 카드 뷰로 다시 렌더링
      if (window.serversData) {
        renderCardView(window.serversData, window.firewallGroups || []);
      }
    }
    
    console.log('[instances.js] 뷰 전환 완료');
  });

  // 서버 검색 기능
  $(document).off('input', '#server-search').on('input', '#server-search', function() {
    const searchTerm = $(this).val().toLowerCase();
    console.log('[instances.js] 서버 검색:', searchTerm);
    
    if (!window.serversData) return;
    
    // 검색 결과 필터링
    const filteredServers = {};
    for (const [name, server] of Object.entries(window.serversData)) {
      if (name.toLowerCase().includes(searchTerm) || 
          (server.role && server.role.toLowerCase().includes(searchTerm)) ||
          (server.ip_addresses && server.ip_addresses.some(ip => ip.includes(searchTerm)))) {
        filteredServers[name] = server;
      }
    }
    
    // 현재 뷰에 따라 렌더링
    const currentView = getCurrentViewType();
    if (currentView === 'table') {
      renderTableView(filteredServers, window.firewallGroups || []);
    } else {
      renderCardView(filteredServers, window.firewallGroups || []);
    }
    
    // 검색 결과 개수 업데이트
    const resultCount = Object.keys(filteredServers).length;
    $('#server-count').text(`${resultCount}개`);
  });

  // 전체 선택/해제 체크박스
  $(document).off('change', '#select-all-servers').on('change', '#select-all-servers', function() {
    const isChecked = $(this).is(':checked');
    $('.server-checkbox').prop('checked', isChecked);
    updateBulkActionsToolbar();
  });

  // 개별 서버 체크박스
  $(document).off('change', '.server-checkbox').on('change', '.server-checkbox', function() {
    updateBulkActionsToolbar();
    
    // 전체 선택 체크박스 상태 업데이트
    const totalCheckboxes = $('.server-checkbox').length;
    const checkedCheckboxes = $('.server-checkbox:checked').length;
    
    if (checkedCheckboxes === 0) {
      $('#select-all-servers').prop('indeterminate', false).prop('checked', false);
    } else if (checkedCheckboxes === totalCheckboxes) {
      $('#select-all-servers').prop('indeterminate', false).prop('checked', true);
    } else {
      $('#select-all-servers').prop('indeterminate', true);
    }
  });

  // 일괄 작업 도구모음 업데이트
  function updateBulkActionsToolbar() {
    const checkedServers = $('.server-checkbox:checked');
    const count = checkedServers.length;
    
    if (count > 0) {
      $('#bulk-actions-btn').prop('disabled', false);
      $('#bulk-actions-toolbar').addClass('show');
      $('#selected-count').text(count);
    } else {
      $('#bulk-actions-btn').prop('disabled', true);
      $('#bulk-actions-toolbar').removeClass('show');
    }
  }

  // 탭 전환 기능
  $(document).off('click', '.bulk-tab-btn').on('click', '.bulk-tab-btn', function() {
    const tabName = $(this).data('tab');
    
    // 탭 버튼 활성화
    $('.bulk-tab-btn').removeClass('active');
    $(this).addClass('active');
    
    // 탭 내용 전환
    $('.bulk-tab-content').removeClass('active');
    $(`#${tabName}-tab`).addClass('active');
    
    // 설정 탭일 때 보안그룹 목록 로드
    if (tabName === 'settings') {
      loadSecurityGroupsForBulk();
    }
  });

  // 보안그룹 목록 로드 (일괄 설정용)
  function loadSecurityGroupsForBulk() {
    $.get('/api/firewall/groups', function(res) {
      if (res.success) {
        let options = '<option value="">보안그룹을 선택하세요</option>';
        options += '<option value="none" class="text-muted">🚫 보안그룹 없음 (해제)</option>';
        res.groups.forEach(function(group) {
          options += `<option value="${group.name}">${group.name} (${group.description || '설명 없음'})</option>`;
        });
        $('#bulk-security-group-select').html(options);
      }
    }).fail(function(xhr) {
      console.error('보안그룹 목록 로드 실패:', xhr);
      $('#bulk-security-group-select').html('<option value="">로드 실패</option>');
    });
  }

  // 일괄 작업 함수들 (새로운 API 사용)
  window.bulkStartServers = function() {
    const serverNames = getSelectedServerNames();
    if (serverNames.length === 0) return;
    
    if (confirm(`선택된 ${serverNames.length}개 서버를 시작하시겠습니까?`)) {
      console.log('[instances.js] 일괄 시작:', serverNames);
      executeBulkAction(serverNames, 'start');
    }
  };

  window.bulkStopServers = function() {
    const serverNames = getSelectedServerNames();
    if (serverNames.length === 0) return;
    
    if (confirm(`선택된 ${serverNames.length}개 서버를 중지하시겠습니까?`)) {
      console.log('[instances.js] 일괄 중지:', serverNames);
      executeBulkAction(serverNames, 'stop');
    }
  };

  window.bulkRebootServers = function() {
    const serverNames = getSelectedServerNames();
    if (serverNames.length === 0) return;
    
    if (confirm(`선택된 ${serverNames.length}개 서버를 재시작하시겠습니까?`)) {
      console.log('[instances.js] 일괄 재시작:', serverNames);
      executeBulkAction(serverNames, 'reboot');
    }
  };

  window.bulkDeleteServers = function() {
    const serverNames = getSelectedServerNames();
    if (serverNames.length === 0) return;
    
    if (confirm(`선택된 ${serverNames.length}개 서버를 삭제하시겠습니까?\n\n⚠️ 이 작업은 되돌릴 수 없습니다!`)) {
      console.log('[instances.js] 일괄 삭제:', serverNames);
      executeBulkAction(serverNames, 'delete');
    }
  };

  // 일괄 작업 API 호출
  function executeBulkAction(serverNames, action) {
    console.log(`[instances.js] 일괄괄 작업 실행: ${action} - ${serverNames.length}개 서버`);
    
    // 일괄 작업 시작 플래그 설정
    isBulkOperationInProgress = true;
    console.log('[instances.js] 일괄 작업 시작 - 자동 새로고침 비활성화');
    
    // 새로고침 버튼 상태 업데이트
    updateRefreshButtonState();
    
    // 선택 해제 및 도구모음 숨김
    clearSelection();
    
    // 일괄 작업 API 호출
    $.ajax({
      url: '/api/servers/bulk_action',
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({
        server_names: serverNames,
        action: action
      }),
      success: function(res) {
        if (res.success) {
          const actionNames = {
            'start': '시작',
            'stop': '중지',
            'reboot': '재시작', 
            'delete': '삭제'
          };
          const actionName = actionNames[action] || action;
          
          addSystemNotification('success', '일괄 작업', res.message);
          
          // SSE를 통해 실시간 알림 수신 (폴링 제거)
          console.log(`[instances.js] 일괄 작업 시작: ${actionName} - ${serverNames.length}개 서버`);
        } else {
          addSystemNotification('error', '일괄 작업', '일괄 작업 요청 실패');
        }
      },
      error: function(xhr) {
        const errorMsg = xhr.responseJSON?.error || xhr.statusText || '알 수 없는 오류';
        addSystemNotification('error', '일괄 작업', `일괄 작업 실패: ${errorMsg}`);
        console.error('[instances.js] 일괄 작업 실패:', xhr);
      }
    });
  }

  window.clearSelection = function() {
    $('.server-checkbox, #select-all-servers').prop('checked', false);
    updateBulkActionsToolbar();
  };

  // 일괄 역할 할당 실행 (설정 탭에서 호출)
  window.executeBulkRoleAssignment = function() {
    const serverNames = getSelectedServerNames();
    const role = $('#bulk-role-select').val();
    
    if (serverNames.length === 0) {
      addSystemNotification('warning', '서버 선택', '할당할 서버를 선택해주세요.');
      return;
    }
    
    if (!role || role === '') {
      addSystemNotification('warning', '역할 선택', '할당할 역할을 선택해주세요.');
      return;
    }
    
    console.log(`[instances.js] 일괄 역할 할당: ${serverNames.length}개 서버 - ${role}`);
    
    // 일괄 작업 시작 플래그 설정
    isBulkOperationInProgress = true;
    console.log('[instances.js] 일괄 역할 할당 시작 - 자동 새로고침 비활성화');
    
    // 새로고침 버튼 상태 업데이트
    updateRefreshButtonState();
    
    // 선택 해제 및 도구모음 숨김
    clearSelection();
    
    // 시작 알림
    const actionText = role === 'none' ? '역할을 해제' : `${role} 역할을 할당`;
    addSystemNotification('info', '일괄 역할 할당', `${serverNames.length}개 서버에 ${actionText}하는 중...`);
    
    // 일괄 역할 할당 API 호출
    $.ajax({
      url: '/api/roles/assign_bulk',
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({
        server_names: serverNames,
        role: role
      }),
      success: function(res) {
        console.log('[instances.js] 일괄 역할 할당 성공:', res);
        
        if (res.task_id) {
          // Task 진행 상황 모니터링
          pollTaskStatus(res.task_id, 'assign_roles_bulk', `${serverNames.length}개 서버`);
        } else {
          // 즉시 완료된 경우
          addSystemNotification('success', '일괄 역할 할당', `${serverNames.length}개 서버에 ${role} 역할이 성공적으로 할당되었습니다.`);
        }
      },
      error: function(xhr) {
        console.error('[instances.js] 일괄 역할 할당 실패:', xhr);
        
        // 일괄 작업 플래그 해제
        isBulkOperationInProgress = false;
        updateRefreshButtonState();
        
        let errorMsg = '알 수 없는 오류';
        if (xhr.status === 403) {
          errorMsg = '권한이 없습니다. 역할 할당 권한이 필요합니다.';
        } else if (xhr.responseJSON?.error) {
          errorMsg = xhr.responseJSON.error;
        }
        
        addSystemNotification('error', '일괄 역할 할당', `${serverNames.length}개 서버 역할 할당 실패: ${errorMsg}`);
      }
    });
  };

  // 일괄 보안그룹 할당 (새로운 함수)
  window.bulkAssignSecurityGroup = function() {
    const serverNames = getSelectedServerNames();
    const securityGroup = $('#bulk-security-group-select').val();
    
    if (serverNames.length === 0) {
      addSystemNotification('warning', '서버 선택', '할당할 서버를 선택해주세요.');
      return;
    }
    
    if (!securityGroup) {
      addSystemNotification('warning', '보안그룹 선택', '할당할 보안그룹을 선택해주세요.');
      return;
    }
    
    console.log(`[instances.js] 일괄 보안그룹 할당: ${serverNames.length}개 서버 - ${securityGroup}`);
    
    // 일괄 작업 시작 플래그 설정
    isBulkOperationInProgress = true;
    console.log('[instances.js] 일괄 보안그룹 할당 시작 - 자동 새로고침 비활성화');
    
    // 새로고침 버튼 상태 업데이트
    updateRefreshButtonState();
    
    // 선택 해제 및 도구모음 숨김
    clearSelection();
    
    // 시작 알림
    addSystemNotification('info', '일괄 보안그룹 할당', `${serverNames.length}개 서버에 ${securityGroup} 보안그룹을 할당하는 중...`);
    
    // 일괄 보안그룹 할당 API 호출
    $.ajax({
      url: '/api/firewall/assign_bulk',
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({
        server_names: serverNames,
        security_group: securityGroup
      }),
      success: function(res) {
        console.log('[instances.js] 일괄 보안그룹 할당 성공:', res);
        
        if (res.task_id) {
          // Task 진행 상황 모니터링
          pollTaskStatus(res.task_id, 'assign_security_groups_bulk', `${serverNames.length}개 서버`);
        } else {
          // 즉시 완료된 경우
          addSystemNotification('success', '일괄 보안그룹 할당', `${serverNames.length}개 서버에 ${securityGroup} 보안그룹이 성공적으로 할당되었습니다.`);
          loadActiveServers();
        }
      },
      error: function(xhr) {
        console.error('[instances.js] 일괄 보안그룹 할당 실패:', xhr);
        
        // 일괄 작업 플래그 해제
        isBulkOperationInProgress = false;
        updateRefreshButtonState();
        
        let errorMsg = '알 수 없는 오류';
        if (xhr.status === 403) {
          errorMsg = '권한이 없습니다. 보안그룹 할당 권한이 필요합니다.';
        } else if (xhr.responseJSON?.error) {
          errorMsg = xhr.responseJSON.error;
        }
        
        addSystemNotification('error', '일괄 보안그룹 할당', `${serverNames.length}개 서버 보안그룹 할당 실패: ${errorMsg}`);
      }
    });
  };

  // 선택된 서버 이름들 가져오기
  function getSelectedServerNames() {
    return $('.server-checkbox:checked').map(function() {
      return $(this).val();
    }).get();
  }

  // 서버 액션 실행 (기존 함수 활용)
  function executeServerAction(serverName, action) {
    const $serverElement = $(`[data-server="${serverName}"]`);
    let $actionBtn;
    
    switch(action) {
      case 'start':
        $actionBtn = $serverElement.find('.start-btn');
        break;
      case 'stop':
        $actionBtn = $serverElement.find('.stop-btn');
        break;
      case 'reboot':
        $actionBtn = $serverElement.find('.reboot-btn');
        break;
      case 'delete':
        $actionBtn = $serverElement.find('.delete-btn');
        break;
      default:
        return;
    }
    
    if ($actionBtn.length > 0 && !$actionBtn.prop('disabled')) {
      $actionBtn.trigger('click');
    }
  }

  // 모든 알림 삭제는 navigation.js에서 중앙 관리됨

  // 네트워크 추가 버튼 클릭 시 네트워크 입력란 추가 (중복 바인딩 방지)
  $(document).off('click', '.add-network-btn').on('click', '.add-network-btn', function() {
    const $container = $('#network-container-basic');
    const $item = $container.find('.network-item').first().clone();
    $item.find('input, select').val('');
    $item.find('.remove-network-btn').prop('disabled', false);
    $container.append($item);
  });

  // 디스크 추가 버튼 클릭 시 디스크 입력란 추가 (중복 바인딩 방지)
  $(document).off('click', '.add-disk-btn').on('click', '.add-disk-btn', function() {
    const $container = $('#disk-container-basic');
    const $item = $container.find('.disk-item').first().clone();
    $item.find('input, select').val('');
    $item.find('.remove-disk-btn').prop('disabled', false);
    
    // datastore 옵션 동적 생성
    loadDatastores().then(function(config) {
      const $datastoreSelect = $item.find('.disk-datastore');
      $datastoreSelect.empty();
      
      // datastore가 없으면 자동으로 새로고침
      if (!config.datastores || config.datastores.length === 0) {
        console.log('[instances.js] 디스크 추가 시 datastore가 없음. 자동으로 새로고침 중...');
        $.post('/api/datastores/refresh')
          .then(function(refreshResponse) {
            if (refreshResponse.success) {
              console.log('[instances.js] 디스크 추가 시 Datastore 새로고침 완료:', refreshResponse.count, '개');
              // 새로고침 후 다시 조회
              return $.get('/api/datastores');
            } else {
              throw new Error('Datastore 새로고침 실패');
            }
          })
          .then(function(newResponse) {
            if (newResponse.success) {
              console.log('[instances.js] 디스크 추가 시 새로고침 후 Datastore 목록 로드 완료:', newResponse.datastores);
              // 새로고침된 데이터로 옵션 생성
              newResponse.datastores.forEach(function(datastore) {
                const isSelected = datastore.id === newResponse.default_hdd ? 'selected' : '';
                const typeLabel = datastore.type === 'lvm' ? 'LVM' : 
                                 datastore.type === 'dir' ? 'Directory' : 
                                 datastore.type === 'nfs' ? 'NFS' : 
                                 datastore.type.toUpperCase();
                
                $datastoreSelect.append(`<option value="${datastore.id}" ${isSelected}>${datastore.name} (${typeLabel})</option>`);
              });
            } else {
              throw new Error('새로고침 후 Datastore 목록 로드 실패');
            }
          })
          .fail(function(error) {
            console.error('[instances.js] 디스크 추가 시 Datastore 새로고침 실패:', error);
            // 실패 시 기본값 사용
            $datastoreSelect.append('<option value="local-lvm" selected>local-lvm (LVM)</option>');
            $datastoreSelect.append('<option value="local">local (Directory)</option>');
          });
      } else {
        // 기존 로직
        config.datastores.forEach(function(datastore) {
          const isSelected = datastore.id === config.default_hdd ? 'selected' : '';
          const typeLabel = datastore.type === 'lvm' ? 'LVM' : 
                           datastore.type === 'dir' ? 'Directory' : 
                           datastore.type === 'nfs' ? 'NFS' : 
                           datastore.type.toUpperCase();
          
          $datastoreSelect.append(`<option value="${datastore.id}" ${isSelected}>${datastore.name} (${typeLabel})</option>`);
        });
      }
    });
    
    $container.append($item);
  });

  // 네트워크 삭제 버튼 클릭 시 (중복 바인딩 방지)
  $(document).off('click', '.remove-network-btn').on('click', '.remove-network-btn', function() {
    const $item = $(this).closest('.network-item');
    const $container = $item.closest('.network-container');
    $item.remove();
    // 마지막 하나 남았을 때 삭제 버튼 비활성화
    if ($container.find('.network-item').length === 1) {
      $container.find('.network-item:first .remove-network-btn').prop('disabled', true);
    }
  });

  // 카드형 서버 생성 모드 UI 연동 (중복 바인딩 방지)
  $(document).off('click', '.mode-card').on('click', '.mode-card', function() {
    $('.mode-card').removeClass('active');
    $(this).addClass('active');
    const mode = $(this).data('mode');
    $('#server_mode').val(mode);
    if (mode === 'multi') {
      $('#multi-server-options').show();
      $('#create-server-btn').text('다음');
    } else {
      $('#multi-server-options').hide();
      $('#create-server-btn').text('서버 생성');
    }
  });

  // 다중 서버 모드: 다음 버튼 클릭 시 요약/수정 모달 표시
  // 이 부분은 이미 위에서 처리되었으므로 제거

  // 일괄 작업 상태에 따른 새로고침 버튼 업데이트
  function updateRefreshButtonState() {
    const $refreshBtn = $('.refresh-btn');
    if (isBulkOperationInProgress) {
      $refreshBtn.addClass('btn-warning').removeClass('btn-refresh');
      $refreshBtn.find('span').text('일괄 작업 중...');
      $refreshBtn.find('i').removeClass('fa-sync-alt').addClass('fa-clock');
      $refreshBtn.prop('title', '일괄 작업 중입니다. 필요시 클릭하여 강제 새로고침');
    } else {
      $refreshBtn.removeClass('btn-warning').addClass('btn-refresh');
      $refreshBtn.find('span').text('새로고침');
      $refreshBtn.find('i').removeClass('fa-clock').addClass('fa-sync-alt');
      $refreshBtn.prop('title', '서버 목록 새로고침');
    }
  }

  // 다중 서버 역할 할당 기능
  $(document).off('click', '.bulk-role-apply').on('click', '.bulk-role-apply', function() {
    const selectedServers = getSelectedServers();
    const selectedRole = $('#bulk-role-select').val();
    
    if (selectedServers.length === 0) {
      alert('역할을 할당할 서버를 선택해주세요.');
      return;
    }
    
    if (!selectedRole) {
      alert('할당할 역할을 선택해주세요.');
      return;
    }
    
    const confirmMessage = `선택된 ${selectedServers.length}개 서버에 '${selectedRole}' 역할을 할당하시겠습니까?`;
    if (!confirm(confirmMessage)) {
      return;
    }
    
    console.log(`[instances.js] 다중 서버 역할 할당 시작: ${selectedServers.join(', ')} → ${selectedRole}`);
    
    // 일괄 작업 플래그 설정
    isBulkOperationInProgress = true;
    updateRefreshButtonState();
    
    $.ajax({
      url: '/api/assign_role_bulk',
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({
        server_names: selectedServers,
        role: selectedRole
      }),
      success: function(response) {
        if (response.success) {
          console.log('[instances.js] 다중 서버 역할 할당 성공:', response);
          
          // 결과 요약 표시
          const summary = response.summary;
          let resultMessage = `다중 서버 역할 할당 완료!\n\n`;
          resultMessage += `총 ${summary.total}개 서버 중 ${summary.success}개 성공, ${summary.failed}개 실패\n\n`;
          
          // 실패한 서버들 표시
          if (summary.failed > 0) {
            const failedServers = response.results.filter(r => !r.success);
            resultMessage += `실패한 서버들:\n`;
            failedServers.forEach(r => {
              resultMessage += `- ${r.server_name}: ${r.message}\n`;
            });
          }
          
          alert(resultMessage);
          
          // 서버 목록 새로고침
          loadActiveServers();
        } else {
          console.error('[instances.js] 다중 서버 역할 할당 실패:', response.error);
          alert(`다중 서버 역할 할당 실패: ${response.error}`);
        }
      },
      error: function(xhr) {
        console.error('[instances.js] 다중 서버 역할 할당 오류:', xhr);
        let errorMsg = '알 수 없는 오류';
        if (xhr.responseJSON?.error) {
          errorMsg = xhr.responseJSON.error;
        }
        alert(`다중 서버 역할 할당 실패: ${errorMsg}`);
      },
      complete: function() {
        // 일괄 작업 플래그 해제
        isBulkOperationInProgress = false;
        updateRefreshButtonState();
      }
    });
  });
  
  // 선택된 서버 목록 가져오기
  function getSelectedServers() {
    const selectedServers = [];
    $('.server-checkbox:checked').each(function() {
      selectedServers.push($(this).val());
    });
    return selectedServers;
  }
  
  // 새로고침 버튼 상태 업데이트
  function updateRefreshButtonState() {
    const $refreshBtn = $('.refresh-btn');
    if (isBulkOperationInProgress) {
      $refreshBtn.prop('disabled', false).text('강제 새로고침');
    } else {
      $refreshBtn.prop('disabled', false).text('새로고침');
    }
  }
});

// =========================
// 알림 시스템은 navigation.js에서 중앙 관리됨
// =========================

// 알림 폴링 제거됨 - navigation.js의 SSE로 대체
(function(){
  // 알림 목록 관리
  window.systemNotifications = window.systemNotifications || [];
  window.addSystemNotification = function(type, title, message, details, id) {
    if (typeof type === 'undefined' && typeof title === 'undefined' && typeof message === 'undefined') {
      // 알림 추가 없이 드롭다운만 갱신
      const $list = $('#notification-list');
      let html = '';
      if (!window.systemNotifications || window.systemNotifications.length === 0) {
        html = '<li class="text-center text-muted py-3">알림이 없습니다</li>';
      }
      $list.html(html);
      $('#notification-badge').hide();
      return;
    }
    // type: 'success' | 'info' | 'error'
    const now = new Date();
    const timeStr = now.toLocaleTimeString('ko-KR', {hour12:false});
    // 알림 객체 추가 (최대 10개 유지)
    window.systemNotifications.unshift({id, type, title, message, details, time: timeStr});
    if (window.systemNotifications.length > 10) window.systemNotifications.length = 10;
    // 드롭다운 렌더링 (상단 네비게이션)
    const $list = $('#notification-list');
    let html = '';
    window.systemNotifications.forEach(function(noti, idx){
      // 에러 타입에 따른 아이콘과 색상 설정
      let icon, textClass;
      if (noti.type === 'success') {
        icon = 'fa-check-circle';
        textClass = 'text-success';
      } else if (noti.type === 'error') {
        icon = 'fa-exclamation-triangle';
        textClass = 'text-danger';
      } else if (noti.type === 'warning') {
        icon = 'fa-exclamation-circle';
        textClass = 'text-warning';
      } else {
        icon = 'fa-info-circle';
        textClass = 'text-info';
      }
      
      // details가 있으면 모달로 표시
      const detailsHtml = (function(){
        if (noti.id) {
          return `
        <div class="mt-2">
          <button class="btn btn-sm btn-outline-primary" type="button" onclick="openNotificationLog(${noti.id})">
            <i class="fas fa-terminal me-1"></i>상세 로그 보기
          </button>
        </div>`;
        }
        if (noti.details) {
          try {
            const titleEnc = encodeURIComponent(noti.title || '상세 로그');
            const detailsB64 = btoa(unescape(encodeURIComponent(String(noti.details))));
            return `
        <div class="mt-2">
          <button class="btn btn-sm btn-outline-primary" type="button" onclick="showLogModalEncoded('${titleEnc}','${detailsB64}')">
            <i class="fas fa-terminal me-1"></i>상세 로그 보기
          </button>
        </div>`;
          } catch(e) { return ''; }
        }
        return '';
      })();
      
      html += `
        <li>
          <div class="dropdown-item d-flex align-items-start small" style="padding: 12px 16px; border-bottom: 1px solid #f0f0f0;">
            <div class="d-flex justify-content-between align-items-start w-100">
              <div class="d-flex align-items-start flex-grow-1">
            <i class="fas ${icon} ${textClass} me-2 mt-1"></i>
            <div class="flex-grow-1">
              <div class="fw-bold mb-1">${noti.title}</div>
              <div class="text-muted" style="word-wrap: break-word; white-space: normal; line-height: 1.5; margin-bottom: 4px;">${noti.message}</div>
                  ${detailsHtml}
              <div class="text-muted small">${noti.time}</div>
                </div>
              </div>
              <button class="btn btn-sm btn-outline-danger ms-2" onclick="deleteNotification('${noti.time.replace(/[^a-zA-Z0-9]/g, '')}')" title="삭제">
                <i class="fas fa-times"></i>
              </button>
            </div>
          </div>
        </li>
      `;
    });
    if (window.systemNotifications.length === 0) {
      html = '<li class="text-center text-muted py-3">알림이 없습니다</li>';
    }
    $list.html(html);
    // 뱃지 갱신
    const $badge = $('#notification-badge');
    if (window.systemNotifications.length > 0) {
      $badge.text(window.systemNotifications.length).show();
    } else {
      $badge.hide();
    }
  };
  
  // 개별 알림 삭제 함수
  window.deleteNotification = function(timeKey) {
    console.log('[instances.js] 개별 알림 삭제:', timeKey);
    
    // 클라이언트에서 해당 알림 제거
    window.systemNotifications = window.systemNotifications.filter(function(noti) {
      return noti.time.replace(/[^a-zA-Z0-9]/g, '') !== timeKey;
    });
    
    // 드롭다운 다시 렌더링
    window.addSystemNotification();
    
    console.log('[instances.js] 개별 알림 삭제 완료');
  };
  
  // 로그 모달 표시 함수
  window.showLogModal = function(title, logContent) {
    console.log('[instances.js] 로그 모달 표시:', title);
    
    // 기존 모달 제거
    $('#logModal').remove();
    
    // 새 모달 생성
    const modalHtml = `
      <div class="modal fade" id="logModal" tabindex="-1" aria-labelledby="logModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-xl modal-dialog-scrollable">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title" id="logModalLabel">
                <i class="fas fa-terminal me-2"></i>${title}
              </h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <div class="bg-dark text-light p-3 rounded" style="font-family: 'Courier New', monospace; font-size: 13px; max-height: 70vh; overflow-y: auto;">
                <pre style="margin: 0; white-space: pre-wrap; color: #00ff00;">${logContent}</pre>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">닫기</button>
              <button type="button" class="btn btn-primary" onclick="copyLogToClipboard()">
                <i class="fas fa-copy me-1"></i>클립보드에 복사
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
    
    // 모달 추가 및 표시
    $('body').append(modalHtml);
    const modal = new bootstrap.Modal(document.getElementById('logModal'));
    modal.show();
  };
  // 알림 ID 기반 상세 로그 열기 (서버에서 안전하게 가져오기)
  window.openNotificationLog = function(notificationId){
    $.get(`/notifications/${notificationId}`)
      .done(function(res){
        if (res && res.success && res.notification){
          const n = res.notification;
          window.showLogModal(n.title || '상세 로그', n.details || n.message || '내용 없음');
        }
      })
      .fail(function(xhr){
        console.error('[instances.js] 알림 상세 조회 실패:', xhr);
      });
  };
  // Base64로 전달된 로그 모달 표시(안전한 인라인 전달용)
  window.showLogModalEncoded = function(titleEnc, detailsB64){
    try {
      const title = decodeURIComponent(titleEnc || '상세 로그');
      let details = '';
      try {
        details = decodeURIComponent(escape(atob(detailsB64)));
      } catch(e) {
        details = atob(detailsB64);
      }
      window.showLogModal(title, details);
    } catch(e) {
      console.error('[instances.js] showLogModalEncoded 오류:', e);
    }
  };
  
  // 로그 클립보드 복사 함수 (호환성 개선)
  window.copyLogToClipboard = function() {
    const logContent = document.querySelector('#logModal pre').textContent;
    
    // 클립보드 API 지원 여부 확인
    if (navigator.clipboard && navigator.clipboard.writeText) {
      // 최신 클립보드 API 사용
      navigator.clipboard.writeText(logContent).then(function() {
        showSuccessToast('로그가 클립보드에 복사되었습니다.');
      }).catch(function(err) {
        console.error('클립보드 복사 실패:', err);
        // 대안 방법 시도
        fallbackCopyToClipboard(logContent);
      });
    } else {
      // 대안 방법 사용
      fallbackCopyToClipboard(logContent);
    }
  };
  
  // 대안 클립보드 복사 방법
  function fallbackCopyToClipboard(text) {
    try {
      // 텍스트 영역 생성
      const textArea = document.createElement('textarea');
      textArea.value = text;
      textArea.style.position = 'fixed';
      textArea.style.left = '-999999px';
      textArea.style.top = '-999999px';
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      
      // 복사 실행
      const successful = document.execCommand('copy');
      document.body.removeChild(textArea);
      
      if (successful) {
        showSuccessToast('로그가 클립보드에 복사되었습니다.');
      } else {
        showErrorToast('클립보드 복사에 실패했습니다.');
      }
    } catch (err) {
      console.error('대안 클립보드 복사 실패:', err);
      showErrorToast('클립보드 복사에 실패했습니다.');
    }
  }
  
  // 성공 토스트 표시
  function showSuccessToast(message) {
    const toast = `
      <div class="toast align-items-center text-white bg-success border-0" role="alert" aria-live="assertive" aria-atomic="true">
        <div class="d-flex">
          <div class="toast-body">
            <i class="fas fa-check me-1"></i>${message}
          </div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
      </div>
    `;
    
    // 토스트 컨테이너가 없으면 생성
    if (!$('#toastContainer').length) {
      $('body').append('<div id="toastContainer" class="toast-container position-fixed top-0 end-0 p-3"></div>');
    }
    
    $('#toastContainer').append(toast);
    const toastElement = new bootstrap.Toast($('#toastContainer .toast').last()[0]);
    toastElement.show();
  }
  
  // 오류 토스트 표시
  function showErrorToast(message) {
    const toast = `
      <div class="toast align-items-center text-white bg-danger border-0" role="alert" aria-live="assertive" aria-atomic="true">
        <div class="d-flex">
          <div class="toast-body">
            <i class="fas fa-exclamation-triangle me-1"></i>${message}
          </div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
      </div>
    `;
    
    // 토스트 컨테이너가 없으면 생성
    if (!$('#toastContainer').length) {
      $('body').append('<div id="toastContainer" class="toast-container position-fixed top-0 end-0 p-3"></div>');
    }
    
    $('#toastContainer').append(toast);
    const toastElement = new bootstrap.Toast($('#toastContainer .toast').last()[0]);
    toastElement.show();
  }

  // Ansible 역할 알림을 SSE로 처리 (폴링 제거)
  // - SSE를 통해 실시간으로 ansible_role 타입 알림 수신
  // - 폴링 방식에서 SSE 방식으로 전환
  window.watchAnsibleRoleNotification = function(serverName){
    console.log(`[instances.js] SSE 전환으로 역할 알림 폴링 비활성화: ${serverName}`);
    // SSE를 통해 실시간 알림 수신하므로 폴링 불필요
    // SSE 이벤트 리스너가 자동으로 ansible_role 타입 알림을 처리함
  };
})();

// Bootstrap 기반 커스텀 confirm 모달 함수
window.confirmModal = function(message) {
  return new Promise(function(resolve) {
    // 기존 confirm 모달이 있으면 제거
    $('#customConfirmModal').remove();
    const html = `
      <div class="modal fade" id="customConfirmModal" tabindex="-1">
        <div class="modal-dialog">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">확인</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <div>${message}</div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">취소</button>
              <button type="button" class="btn btn-primary" id="customConfirmOk">확인</button>
            </div>
          </div>
        </div>
      </div>`;
    $('body').append(html);
    const modal = new bootstrap.Modal(document.getElementById('customConfirmModal'));
    modal.show();
    $('#customConfirmOk').off('click').on('click', function() {
      modal.hide();
      resolve(true);
    });
    $('#customConfirmModal').on('hidden.bs.modal', function(){
      $('#customConfirmModal').remove();
      resolve(false);
    });
  });
};

// Bootstrap 기반 커스텀 alert 모달 함수
window.alertModal = function(message) {
  return new Promise(function(resolve) {
    $('#customAlertModal').remove();
    const html = `
      <div class="modal fade" id="customAlertModal" tabindex="-1">
        <div class="modal-dialog">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">알림</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <div>${message}</div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-primary" id="customAlertOk">확인</button>
            </div>
          </div>
        </div>
      </div>`;
    $('body').append(html);
    const modal = new bootstrap.Modal(document.getElementById('customAlertModal'));
    modal.show();
    $('#customAlertOk').off('click').on('click', function() {
      modal.hide();
      resolve();
    });
    $('#customAlertModal').on('hidden.bs.modal', function(){
      $('#customAlertModal').remove();
      resolve();
    });
  });
};

// =========================
// JavaScript 에러 캐치 및 알림 시스템
// =========================

// 전역 에러 핸들러 설정
window.addEventListener('error', function(event) {
  console.error('[Error Handler] JavaScript 에러 발생:', event);
  
  // 에러 정보 추출
  const errorInfo = {
    message: event.message || '알 수 없는 에러',
    filename: event.filename || '알 수 없는 파일',
    lineno: event.lineno || 0,
    colno: event.colno || 0,
    stack: event.error ? event.error.stack : null
  };
  
  // 에러 메시지 생성
  const fileName = errorInfo.filename.split('/').pop() || '알 수 없는 파일';
  const errorTitle = `🚨 JavaScript 에러`;
  const errorMessage = `${fileName}: ${errorInfo.message} (라인 ${errorInfo.lineno})`;
  
  // 알림에 추가
  window.addSystemNotification('error', errorTitle, errorMessage, {
    type: 'javascript_error',
    filename: errorInfo.filename,
    lineno: errorInfo.lineno,
    colno: errorInfo.colno,
    stack: errorInfo.stack,
    fullError: errorInfo
  });
  
  // 개발자 도구에도 로그
  console.group('🚨 JavaScript 에러 상세 정보');
  console.error('메시지:', errorInfo.message);
  console.error('파일:', errorInfo.filename);
  console.error('라인:', errorInfo.lineno, '컬럼:', errorInfo.colno);
  if (errorInfo.stack) {
    console.error('스택 트레이스:', errorInfo.stack);
  }
  console.groupEnd();
});

// Promise rejection 에러 핸들러
window.addEventListener('unhandledrejection', function(event) {
  console.error('[Error Handler] Promise rejection 발생:', event);
  
  // 에러 정보 추출
  const reason = event.reason;
  const errorTitle = '🚨 Promise Rejection';
  let errorMessage = '알 수 없는 Promise 에러';
  
  if (typeof reason === 'string') {
    errorMessage = reason;
  } else if (reason && reason.message) {
    errorMessage = reason.message;
  } else if (reason && reason.toString) {
    errorMessage = reason.toString();
  }
  
  // 알림에 추가
  window.addSystemNotification('error', errorTitle, errorMessage, {
    type: 'promise_rejection',
    reason: reason,
    fullError: event
  });
  
  // 개발자 도구에도 로그
  console.group('🚨 Promise Rejection 상세 정보');
  console.error('Reason:', reason);
  console.groupEnd();
});

// SSE는 navigation.js에서 중앙 관리됨
// instances.js에서는 SSE 이벤트 처리만 담당

// 페이지 로드 시 SSE 연결
$(document).ready(function() {
  initNotificationStream();
});

// AJAX 에러 전역 핸들러 (jQuery)
$(document).ajaxError(function(event, xhr, settings, thrownError) {
  console.error('[Error Handler] AJAX 에러 발생:', {
    url: settings.url,
    method: settings.type,
    status: xhr.status,
    error: thrownError
  });
  
  // 500 에러나 심각한 에러만 알림에 추가 (너무 많은 알림 방지)
  if (xhr.status >= 500 || xhr.status === 0) {
    const errorTitle = `🚨 AJAX 에러 (${xhr.status})`;
    const urlPath = settings.url.split('/').pop() || settings.url;
    const errorMessage = `${settings.type || 'GET'} ${urlPath} - ${thrownError || '서버 에러'}`;
    
    window.addSystemNotification('error', errorTitle, errorMessage, {
      type: 'ajax_error',
      url: settings.url,
      method: settings.type,
      status: xhr.status,
      responseText: xhr.responseText ? xhr.responseText.substring(0, 500) : null,
      fullError: { xhr, settings, thrownError }
    });
  }
});

// 콘솔 에러 메시지 캐치 (선택적)
if (window.console && window.console.error) {
  const originalError = window.console.error;
  window.console.error = function(...args) {
    // 원본 함수 호출
    originalError.apply(console, args);
    
    // 특정 패턴의 에러만 알림에 추가 (너무 많은 알림 방지)
    const message = args.join(' ');
    if (message.includes('404') || message.includes('500') || message.includes('TemplateNotFound') || message.includes('jinja2') || message.includes('jinja2.exceptions')) {
      const errorTitle = '🚨 시스템 에러';
      const errorMessage = message.length > 100 ? message.substring(0, 100) + '...' : message;
      
      window.addSystemNotification('error', errorTitle, errorMessage, {
        type: 'console_error',
        fullMessage: message,
        originalArgs: args
      });
    }
  };
}

console.log('[instances.js] JavaScript 에러 캐치 시스템 활성화됨');

// 테스트용 에러 발생 함수 (개발 환경에서만 사용)
window.testErrorCapture = function() {
  console.log('[Test] 에러 캐치 시스템 테스트 시작');
  
  // JavaScript 에러 테스트
  setTimeout(() => {
    try {
      throw new Error('테스트 JavaScript 에러입니다');
    } catch (e) {
      // 의도적으로 에러를 다시 던져서 전역 핸들러가 캐치하도록 함
      setTimeout(() => { throw e; }, 100);
    }
  }, 1000);
  
  // Promise rejection 테스트
  setTimeout(() => {
    Promise.reject('테스트 Promise rejection 에러입니다');
  }, 2000);
  
  // AJAX 에러 테스트
  setTimeout(() => {
    $.get('/nonexistent-endpoint-for-testing');
  }, 3000);
  
  console.log('[Test] 에러 테스트가 1초, 2초, 3초 후에 순차적으로 실행됩니다');
}; 
// app/static/monitoring.js
$(document).ready(function() {
    // ============================================================================
    // 🚀 모니터링 시스템 설정 변수들
    // ============================================================================
    
    // API 엔드포인트 설정
    const API_BASE_URL = '/monitoring';
    const SERVERS_API = `${API_BASE_URL}/servers`;
    
    // 서버 상태 정의
    const SERVER_STATUS = {
        HEALTHY: 'healthy',
        WARNING: 'warning',
        CRITICAL: 'critical'
    };
    
    // ============================================================================
    // 🔧 전역 변수들
    // ============================================================================
    let selectedServer = 'all';
    let servers = [];
    let grafanaDashboardInfo = null;
    
    // 스마트 모니터링 시스템 변수들
    let serverStatusCache = new Map(); // 서버 상태 캐시
    let lastUpdateTime = null; // 마지막 업데이트 시간
    let updateInterval = 5 * 60 * 1000; // 5분 간격 (밀리초)
    let backgroundUpdateTimer = null; // 백그라운드 업데이트 타이머
    let isUpdating = false; // 업데이트 중 플래그
    
    // ============================================================================
    // �� 초기화 및 메인 실행
    // ============================================================================
    init();
    
    function init() {
        // 스마트 모니터링 시스템 초기화
        initSmartMonitoring();
        
        setupEventListeners();
        initializeGrafanaDashboard(); // iframe만 사용
    }
    
    // ============================================================================
    // 🧠 스마트 모니터링 시스템
    // ============================================================================
    
    // 스마트 모니터링 시스템 초기화
    function initSmartMonitoring() {
        console.log('🧠 스마트 모니터링 시스템 초기화');
        
        // 초기 서버 데이터 로딩
        loadServersDataSmart();
        
        // 백그라운드 업데이트 시작
        startBackgroundUpdate();
        
        // 페이지 가시성 변경 감지 (탭 전환 시 업데이트)
        document.addEventListener('visibilitychange', handleVisibilityChange);
    }
    
    // 스마트 서버 데이터 로딩
    function loadServersDataSmart() {
        if (isUpdating) {
            console.log('⏳ 이미 업데이트 중입니다. 건너뜀.');
            return;
        }
        
        console.log('🔄 스마트 서버 데이터 로딩 시작');
        isUpdating = true;
        
        $.getJSON(SERVERS_API)
            .then(function(response) {
                if (response.success) {
                    const allServers = response.data;
                    
                    // Cloud-init 및 유효하지 않은 서버 필터링
                    const validServers = allServers.filter(server => {
                        // Cloud-init 서버 제외
                        if (server.name && server.name.toLowerCase().includes('cloud-init')) {
                            return false;
                        }
                        
                        // IP가 0.0.0.0인 서버 제외
                        if (server.ip === '0.0.0.0' || server.ip === '127.0.0.1') {
                            return false;
                        }
                        
                        // 이름이 없는 서버 제외
                        if (!server.name || server.name.trim() === '') {
                            return false;
                        }
                        
                        return true;
                    });
                    
                    console.log(`📊 서버 필터링 결과: ${validServers.length}개 (전체: ${allServers.length}개)`);
                    
                    const hasChanges = updateServerStatusCache(validServers);
                    
                    if (hasChanges) {
                        console.log('✅ 서버 상태 변경 감지됨. UI 업데이트');
                        servers = validServers; // 필터링된 서버만 사용
                        loadServersOverview();
                        populateServerDropdown();
                        lastUpdateTime = new Date();
                        updateLastUpdateTime();
                    } else {
                        console.log('ℹ️ 서버 상태 변경 없음. UI 업데이트 건너뜀');
                        // 변경이 없어도 시간은 업데이트
                        lastUpdateTime = new Date();
                        updateLastUpdateTime();
                    }
                }
            })
            .catch(function(error) {
                console.error('❌ 서버 데이터 로딩 실패:', error);
                // 오류 발생 시 기본값 설정
                servers = [];
                loadServersOverview();
            })
            .always(function() {
                isUpdating = false;
            });
    }
    
    // 서버 상태 캐시 업데이트 및 변경 감지
    function updateServerStatusCache(newServers) {
        let hasChanges = false;
        
        // Cloud-init 및 유효하지 않은 서버 필터링
        const validServers = newServers.filter(server => {
            // Cloud-init 서버 제외
            if (server.name && server.name.toLowerCase().includes('cloud-init')) {
                console.log(`🚫 Cloud-init 서버 제외: ${server.name} (${server.ip})`);
                return false;
            }
            
            // IP가 0.0.0.0인 서버 제외
            if (server.ip === '0.0.0.0' || server.ip === '127.0.0.1') {
                console.log(`🚫 로컬/무효 IP 서버 제외: ${server.name} (${server.ip})`);
                return false;
            }
            
            // 이름이 없는 서버 제외
            if (!server.name || server.name.trim() === '') {
                console.log(`🚫 이름 없는 서버 제외: ${server.ip}`);
                return false;
            }
            
            return true;
        });
        
        console.log(`📊 유효한 서버: ${validServers.length}개 (전체: ${newServers.length}개)`);
        
        validServers.forEach(server => {
            const serverKey = `${server.ip}_${server.vmid}`;
            const cachedStatus = serverStatusCache.get(serverKey);
            const currentStatus = server.status;
            
            if (cachedStatus !== currentStatus) {
                console.log(`🔄 서버 상태 변경: ${server.name} (${server.ip}) - ${cachedStatus} → ${currentStatus}`);
                serverStatusCache.set(serverKey, currentStatus);
                hasChanges = true;
            }
        });
        
        // 새로운 서버 추가 감지
        if (serverStatusCache.size !== validServers.length) {
            console.log('🆕 새로운 서버 감지됨');
            hasChanges = true;
            
            // 캐시 초기화
            serverStatusCache.clear();
            validServers.forEach(server => {
                const serverKey = `${server.ip}_${server.vmid}`;
                serverStatusCache.set(serverKey, server.status);
            });
        }
        
        return hasChanges;
    }
    
    // 백그라운드 업데이트 시작
    function startBackgroundUpdate() {
        console.log(`⏰ 백그라운드 업데이트 시작 (${updateInterval / 1000}초 간격)`);
        
        backgroundUpdateTimer = setInterval(() => {
            // 페이지가 보이는 상태일 때만 업데이트
            if (!document.hidden) {
                loadServersDataSmart();
            }
        }, updateInterval);
    }
    
    // 백그라운드 업데이트 중지
    function stopBackgroundUpdate() {
        if (backgroundUpdateTimer) {
            clearInterval(backgroundUpdateTimer);
            backgroundUpdateTimer = null;
            console.log('⏹️ 백그라운드 업데이트 중지');
        }
    }
    
    // 페이지 가시성 변경 처리
    function handleVisibilityChange() {
        if (document.hidden) {
            console.log('👁️ 페이지 숨김 - 백그라운드 업데이트 일시 중지');
            stopBackgroundUpdate();
        } else {
            console.log('👁️ 페이지 표시 - 백그라운드 업데이트 재시작');
            startBackgroundUpdate();
            
            // 페이지가 다시 보일 때 즉시 업데이트
            setTimeout(() => {
                loadServersDataSmart();
            }, 1000);
        }
    }
    
    // 수동 새로고침 (사용자 요청 시)
    function forceRefresh() {
        console.log('🔄 수동 새로고침 요청');
        serverStatusCache.clear(); // 캐시 초기화
        loadServersDataSmart();
    }
    
    // 마지막 업데이트 시간 표시
    function updateLastUpdateTime() {
        if (lastUpdateTime) {
            const timeString = lastUpdateTime.toLocaleString('ko-KR', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            $('#update-time').text(timeString);
        }
    }
    
    // ============================================================================
    // �� 서버 데이터 로딩 및 관리
    // ============================================================================
    
    // 서버 데이터 로딩 (레거시 - 스마트 버전 사용 권장)
    function loadServersData() {
        console.log('⚠️ 레거시 loadServersData 호출됨. 스마트 버전으로 리다이렉트');
        loadServersDataSmart();
    }
    
    // 서버 개요 로딩
    function loadServersOverview() {
        updateSummaryPanels();
        updateStatusBadge();
    }
    
    // 요약 패널 업데이트
    function updateSummaryPanels() {
        try {
            console.log('updateSummaryPanels 호출됨');
            
            // 서버 데이터 검증
            if (!servers || !Array.isArray(servers)) {
                console.warn('서버 데이터가 없거나 유효하지 않습니다.');
                servers = [];
            }
            
            const total = servers.length;
            const healthy = servers.filter(s => s.status === 'healthy').length;
            const warning = servers.filter(s => s.status === 'warning').length;
            const critical = servers.filter(s => s.status === 'critical').length;
            
            console.log(`서버 통계: 전체=${total}, 정상=${healthy}, 경고=${warning}, 위험=${critical}`);
            
            // 요약 패널 업데이트
            $('#total-servers').text(total);
            $('#healthy-servers').text(healthy);
            $('#warning-servers').text(warning);
            $('#critical-servers').text(critical);
            
            // 경고/위험 서버가 있으면 상세 정보 패널 표시
            if (warning > 0 || critical > 0) {
                $('#server-alerts-panel').show();
                displayServerAlerts();
            } else {
                $('#server-alerts-panel').hide();
            }
            
            // 상태별 배지 색상 업데이트
            updateStatusBadge();
            
        } catch (error) {
            console.error('요약 패널 업데이트 오류:', error);
            // 오류 발생 시 기본값 설정
            $('#total-servers').text('0');
            $('#healthy-servers').text('0');
            $('#warning-servers').text('0');
            $('#critical-servers').text('0');
        }
    }
    
    // 서버 드롭다운 채우기 - 서버 이름 기반
    function populateServerDropdown() {
        try {
            console.log('populateServerDropdown 호출됨');
            
            const select = $('#server-select');
            select.empty();
            
            // 서버 데이터 검증
            if (!servers || !Array.isArray(servers)) {
                console.warn('서버 드롭다운 초기화: 서버 데이터가 없습니다.');
                servers = [];
            }
            
            // 전체 서버 옵션 추가
            select.append('<option value="all">🖥️ 전체 서버</option>');
            
            // 개별 서버 옵션 추가 (서버 이름 기반)
            if (servers.length > 0) {
                servers.forEach(server => {
                    // 서버 이름과 IP를 함께 표시
                    const displayName = `${server.name} (${server.ip})`;
                    const option = `<option value="${server.ip}" data-name="${server.name}">${displayName}</option>`;
                    select.append(option);
                });
                console.log(`${servers.length}개 서버 옵션 추가됨 (이름 기반)`);
            } else {
                // 서버가 없을 때 기본 옵션 추가
                select.append('<option value="none" disabled>서버가 없습니다</option>');
                console.log('서버가 없어서 기본 옵션만 표시');
            }
            
        } catch (error) {
            console.error('서버 드롭다운 초기화 오류:', error);
            // 오류 발생 시 기본 옵션만 표시
            const select = $('#server-select');
            select.empty();
            select.append('<option value="all">🖥️ 전체 서버</option>');
            select.append('<option value="none" disabled>서버 로드 실패</option>');
        }
    }
    
    // 상태 배지 업데이트
    function updateStatusBadge() {
        const selectedServerData = servers.find(s => s.ip === selectedServer) || { status: SERVER_STATUS.HEALTHY };
        const $badge = $('#status-badge');
        const $lastUpdate = $('#last-update');

        $badge.removeClass().addClass('badge me-2');
        
        switch(selectedServerData.status) {
            case SERVER_STATUS.HEALTHY:
                $badge.addClass('bg-success').html('정상');
                break;
            case SERVER_STATUS.WARNING:
                $badge.addClass('bg-warning').html('경고');
                break;
            case SERVER_STATUS.CRITICAL:
                $badge.addClass('bg-danger').html('위험');
                break;
        }

        $lastUpdate.text(`마지막 업데이트: ${new Date().toLocaleTimeString()}`);
    }
    
    // ============================================================================
    // �� 이벤트 리스너 및 사용자 인터페이스
    // ============================================================================
    
    // 이벤트 리스너 설정
    function setupEventListeners() {
        // 서버 선택 변경
        $('#server-select').on('change', function() {
            const newSelectedServer = $(this).val();
            console.log('🎯 서버 선택 이벤트 발생:', {
                old: selectedServer,
                new: newSelectedServer,
                option: $(this).find('option:selected').text()
            });
            
            selectedServer = newSelectedServer;
            updateStatusBadge();
            window.updateGrafanaDashboard(); // 서버 선택 변경 시 Grafana 대시보드 업데이트
        });

        // 새로고침 버튼
        $('#refresh-btn').on('click', function() {
            refreshData();
        });

        // Grafana 대시보드 새로고침 버튼
        $('#grafana-refresh-btn').on('click', function() {
            window.refreshGrafanaDashboard();
        });

        // Grafana 전체화면 버튼
        $('#grafana-fullscreen-btn').on('click', function() {
            openGrafanaFullscreen();
        });
    }
    
    // ============================================================================
    // 🎯 Grafana 대시보드 iframe 임베딩 관리
    // ============================================================================
    
    // Grafana 대시보드 초기화
    function initializeGrafanaDashboard() {
        console.log('Grafana 대시보드 초기화 시작');
        
        // Grafana 대시보드 정보 가져오기
        $.getJSON('/monitoring/grafana-dashboard')
            .then(function(response) {
                if (response.success && response.data) {
                    grafanaDashboardInfo = response.data;
                    console.log('Grafana 대시보드 정보 로드 완료:', grafanaDashboardInfo);
                    
                    // 초기 대시보드 표시
                    displayGrafanaDashboard('all');
                } else {
                    console.error('Grafana 대시보드 정보 로드 실패:', response);
                    showGrafanaError('Grafana 대시보드 정보를 가져올 수 없습니다.');
                }
            })
            .catch(function(error) {
                console.error('Grafana 대시보드 초기화 실패:', error);
                showGrafanaError('Grafana 대시보드에 연결할 수 없습니다.');
            });
    }
    
    // Grafana 대시보드 표시
    function displayGrafanaDashboard(selectedServer) {
        if (!grafanaDashboardInfo) {
            console.warn('⚠️ Grafana 대시보드 정보가 없습니다.');
            return;
        }
        
        console.log('📊 Grafana 대시보드 표시 시작:', {
            selectedServer: selectedServer,
            dashboardInfo: grafanaDashboardInfo
        });
        
        // 로딩 표시
        $('#grafana-loading').show();
        $('#grafana-dashboard').hide();
        hideGrafanaError();
        
        // 서버별 임베드 URL 생성
        const embedUrl = generateGrafanaEmbedUrl(selectedServer);
        console.log('🔗 생성된 임베드 URL:', embedUrl);
        
        // iframe 생성 및 설정
        const iframe = document.createElement('iframe');
        iframe.src = embedUrl;
        iframe.width = '100%';
        iframe.height = '800';
        iframe.frameBorder = '0';
        iframe.allowFullscreen = true;
        iframe.style.border = 'none';
        iframe.style.borderRadius = '8px';
        iframe.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
        
        // iframe 로드 완료 이벤트
        iframe.onload = function() {
            console.log('✅ Grafana 대시보드 로드 완료');
            $('#grafana-loading').hide();
            $('#grafana-dashboard').show();
        };
        
        // iframe 로드 오류 이벤트
        iframe.onerror = function() {
            console.error('❌ Grafana 대시보드 로드 실패');
            $('#grafana-loading').hide();
            showGrafanaError('Grafana 대시보드를 로드할 수 없습니다.');
        };
        
        // 기존 iframe 제거 후 새 iframe 추가
        const container = document.getElementById('grafana-dashboard');
        container.innerHTML = '';
        container.appendChild(iframe);
        
        console.log('🔄 iframe 교체 완료');
    }
    
    // Grafana 임베드 URL 생성 - 개선된 서버 필터링
    function generateGrafanaEmbedUrl(selectedServer) {
        if (!grafanaDashboardInfo) {
            return '';
        }
        
        const baseUrl = grafanaDashboardInfo.base_url;
        const dashboardUid = grafanaDashboardInfo.dashboard_uid;
        const orgId = grafanaDashboardInfo.org_id;
        
        // 기본 임베드 URL (자동 새로고침 포함)
        let embedUrl = `${baseUrl}/d/${dashboardUid}?orgId=${orgId}&theme=light&kiosk=tv&autofitpanels&refresh=5s`;
        
        // 서버별 필터링 - 여러 형식 시도
        if (selectedServer && selectedServer !== 'all') {
            console.log(`🔍 서버 필터링 시도: ${selectedServer}`);
            
            // Grafana에서 실제 사용하는 변수명 (var-server) 우선 사용
            const serverFilters = [
                `&var-server=${selectedServer}:9100`,   // Grafana에서 실제 사용하는 형식
                `&var-server=${selectedServer}`,        // server 변수명, 포트 없이
                `&var-instance=${selectedServer}:9100`,  // instance 변수명 (Node Exporter 포트)
                `&var-instance=${selectedServer}`,       // instance 변수명, 포트 없이
                `&var-host=${selectedServer}:9100`,     // host 변수명
                `&var-host=${selectedServer}`,          // host 변수명, 포트 없이
                `&var-target=${selectedServer}:9100`,   // target 변수명
                `&var-target=${selectedServer}`,        // target 변수명, 포트 없이
                `&var-node=${selectedServer}:9100`,     // node 변수명
                `&var-node=${selectedServer}`,          // node 변수명, 포트 없이
                `&var-job=node&var-server=${selectedServer}:9100`, // job과 server 조합
                `&var-job=node&var-server=${selectedServer}`,      // job과 server 조합 (포트 없이)
                `&var-datasource=prometheus&var-server=${selectedServer}:9100`, // datasource 포함
                `&var-datasource=prometheus&var-server=${selectedServer}`       // datasource 포함 (포트 없이)
            ];
            
            // 첫 번째 형식 사용 (Grafana에서 실제 사용하는 형식)
            embedUrl += serverFilters[0];
            console.log(`✅ 서버 필터링 적용: ${selectedServer} -> ${serverFilters[0]}`);
            console.log(`🔗 최종 URL: ${embedUrl}`);
        } else {
            console.log(`📊 전체 서버 표시 모드`);
        }
        
        // 시간 범위 설정 (최근 1시간)
        const now = new Date();
        const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
        embedUrl += `&from=${oneHourAgo.getTime()}&to=${now.getTime()}`;
        
        return embedUrl;
    }
    
    // Grafana 오류 표시
    function showGrafanaError(message) {
        const errorHtml = `
            <div class="alert alert-warning d-flex align-items-center" role="alert">
                <i class="fas fa-exclamation-triangle me-2"></i>
                <div>
                    <strong>Grafana 대시보드 오류:</strong> ${message}
                </div>
            </div>
        `;
        $('#grafana-dashboard').html(errorHtml).show();
    }
    
    // Grafana 오류 숨기기
    function hideGrafanaError() {
        $('#grafana-dashboard .alert').remove();
    }
    
    // 서버 선택 변경 시 Grafana 대시보드 업데이트
    window.updateGrafanaDashboard = function() {
        const selectedServer = $('#server-select').val();
        const selectedOption = $('#server-select option:selected');
        const serverName = selectedOption.data('name') || selectedOption.text();
        
        console.log('🔄 서버 선택 변경 감지:', {
            server: serverName,
            ip: selectedServer,
            option: selectedOption.text(),
            grafanaInfo: grafanaDashboardInfo ? '있음' : '없음'
        });
        
        if (selectedServer && grafanaDashboardInfo) {
            console.log('🚀 Grafana 대시보드 업데이트 시작...');
            displayGrafanaDashboard(selectedServer);
        } else {
            console.warn('⚠️ Grafana 대시보드 업데이트 실패:', {
                selectedServer: selectedServer,
                grafanaInfo: grafanaDashboardInfo
            });
        }
    };
    
    // Grafana 대시보드 새로고침
    window.refreshGrafanaDashboard = function() {
        const selectedServer = $('#server-select').val() || 'all';
        console.log('Grafana 대시보드 새로고침:', selectedServer);
        
        // 로딩 표시
        $('#grafana-loading').show();
        $('#grafana-dashboard').hide();
        hideGrafanaError();
        
        // 대시보드 다시 로드
        displayGrafanaDashboard(selectedServer);
    };
    
    // Grafana 전체화면 열기
    function openGrafanaFullscreen() {
        if (!grafanaDashboardInfo) {
            alert('Grafana 대시보드 정보가 없습니다.');
            return;
        }
        
        const selectedServer = $('#server-select').val() || 'all';
        const embedUrl = generateGrafanaEmbedUrl(selectedServer);
        
        if (embedUrl) {
            // 새 창에서 Grafana 대시보드 열기
            window.open(embedUrl, '_blank', 'width=1920,height=1080,scrollbars=yes,resizable=yes');
        } else {
            alert('전체화면 모드를 열 수 없습니다.');
        }
    }
    
    // Grafana 필터 초기화
    window.resetGrafanaFilter = function() {
        $('#server-select').val('all');
        updateGrafanaDashboard();
        console.log('🔄 Grafana 필터 초기화됨');
    };
    
    // Grafana 변수 형식 테스트 (디버깅용)
    window.testGrafanaVariables = function() {
        if (!grafanaDashboardInfo || servers.length === 0) {
            console.warn('⚠️ 테스트를 위한 데이터가 없습니다.');
            return;
        }
        
        const testServer = servers[0].ip;
        console.log('🧪 Grafana 변수 형식 테스트 시작:', testServer);
        
        const baseUrl = grafanaDashboardInfo.base_url;
        const dashboardUid = grafanaDashboardInfo.dashboard_uid;
        const orgId = grafanaDashboardInfo.org_id;
        
        const testFormats = [
            `&var-server=${testServer}:9100`,   // Grafana에서 실제 사용하는 형식
            `&var-server=${testServer}`,        // server 변수명, 포트 없이
            `&var-instance=${testServer}:9100`,  // instance 변수명
            `&var-instance=${testServer}`,       // instance 변수명, 포트 없이
            `&var-host=${testServer}:9100`,     // host 변수명
            `&var-host=${testServer}`,          // host 변수명, 포트 없이
            `&var-target=${testServer}:9100`,   // target 변수명
            `&var-target=${testServer}`,        // target 변수명, 포트 없이
            `&var-node=${testServer}:9100`,     // node 변수명
            `&var-node=${testServer}`,          // node 변수명, 포트 없이
            `&var-job=node&var-server=${testServer}:9100`, // job과 server 조합
            `&var-job=node&var-server=${testServer}`       // job과 server 조합 (포트 없이)
        ];
        
        testFormats.forEach((format, index) => {
            const testUrl = `${baseUrl}/d/${dashboardUid}?orgId=${orgId}&theme=light&kiosk=tv${format}`;
            console.log(`📋 테스트 ${index + 1}: ${format}`);
            console.log(`🔗 URL: ${testUrl}`);
        });
        
        console.log('💡 위 URL들을 브라우저에서 직접 테스트해보세요!');
    };
    
    // ============================================================================
    // 🚨 경고/위험 서버 상세 정보 관리
    // ============================================================================
    
    // 경고/위험 서버 상세 정보 표시
    function displayServerAlerts() {
        try {
            console.log('🚨 경고/위험 서버 상세 정보 표시 시작');
            
            const problematicServers = servers.filter(s => s.status === 'warning' || s.status === 'critical');
            const container = $('#server-alerts-container');
            container.empty();
            
            if (problematicServers.length === 0) {
                container.html('<div class="alert alert-success"><i class="fas fa-check-circle me-2"></i>모든 서버가 정상 상태입니다.</div>');
                return;
            }
            
            problematicServers.forEach(server => {
                const serverAlertCard = createServerAlertCard(server);
                container.append(serverAlertCard);
            });
            
            console.log(`✅ ${problematicServers.length}개 서버의 경고/위험 정보 표시 완료`);
            
        } catch (error) {
            console.error('❌ 경고/위험 서버 상세 정보 표시 오류:', error);
            $('#server-alerts-container').html('<div class="alert alert-danger"><i class="fas fa-exclamation-triangle me-2"></i>서버 정보를 불러올 수 없습니다.</div>');
        }
    }
    
    // 서버 경고 카드 생성
    function createServerAlertCard(server) {
        const statusClass = server.status === 'critical' ? 'danger' : 'warning';
        const statusIcon = server.status === 'critical' ? 'fa-times-circle' : 'fa-exclamation-triangle';
        const statusText = server.status === 'critical' ? '위험' : '경고';
        
        // 서버 상태에 따른 문제점 시뮬레이션
        const issues = generateServerIssues(server);
        
        let issuesHtml = '';
        if (issues && issues.length > 0) {
            issuesHtml = issues.map(issue => {
                const issueClass = issue.level === 'critical' ? 'danger' : 'warning';
                return `
                    <div class="alert alert-${issueClass} alert-sm mb-2">
                        <i class="fas fa-${getIssueIcon(issue.type)} me-2"></i>
                        <strong>${issue.type.toUpperCase()}:</strong> ${issue.message}
                        <span class="badge bg-${issueClass} ms-2">${issue.value}${getIssueUnit(issue.type)}</span>
                    </div>
                `;
            }).join('');
        }
        
        // 메트릭 정보 (실제 API에서 가져오기)
        const metrics = generateServerMetrics(server);
        let metricsHtml = '';
        if (metrics) {
            // 상태별 색상 클래스 결정
            const getStatusColor = (value, type) => {
                if (type === 'network_latency') {
                    if (value > 100) return 'text-danger';
                    if (value > 50) return 'text-warning';
                    return 'text-success';
                } else {
                    if (value > 90) return 'text-danger';
                    if (value > 80) return 'text-warning';
                    return 'text-success';
                }
            };
            
            // 값 포맷팅
            const formatValue = (value, type) => {
                if (type === 'network_latency') {
                    return `${value.toFixed(1)}ms`;
                } else {
                    return `${value.toFixed(1)}%`;
                }
            };
            
            metricsHtml = `
                <div class="row mt-3">
                    <div class="col-md-3">
                        <div class="text-center">
                            <div class="h6 text-muted">CPU</div>
                            <div class="h5 ${getStatusColor(metrics.cpu_usage, 'cpu_usage')}">${formatValue(metrics.cpu_usage, 'cpu_usage')}</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="text-center">
                            <div class="h6 text-muted">메모리</div>
                            <div class="h5 ${getStatusColor(metrics.memory_usage, 'memory_usage')}">${formatValue(metrics.memory_usage, 'memory_usage')}</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="text-center">
                            <div class="h6 text-muted">디스크</div>
                            <div class="h5 ${getStatusColor(metrics.disk_usage, 'disk_usage')}">${formatValue(metrics.disk_usage, 'disk_usage')}</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="text-center">
                            <div class="h6 text-muted">네트워크</div>
                            <div class="h5 ${getStatusColor(metrics.network_latency, 'network_latency')}">${formatValue(metrics.network_latency, 'network_latency')}</div>
                        </div>
                    </div>
                </div>
                <div class="alert alert-info mt-2">
                    <i class="fas fa-info-circle me-2"></i>
                    <strong>참고:</strong> 상세 메트릭은 Grafana 대시보드에서 확인하세요.
                </div>
            `;
        }
        
        return `
            <div class="card border-${statusClass} mb-3">
                <div class="card-header bg-${statusClass} text-white">
                    <div class="row align-items-center">
                        <div class="col">
                            <h6 class="mb-0">
                                <i class="fas ${statusIcon} me-2"></i>
                                ${server.name} (${server.ip}) - ${statusText} 상태
                            </h6>
                        </div>
                        <div class="col-auto">
                            <button type="button" class="btn btn-sm btn-light" onclick="showServerDetail('${server.ip}')">
                                <i class="fas fa-info-circle me-1"></i>상세보기
                            </button>
                        </div>
                    </div>
                </div>
                <div class="card-body">
                    ${issuesHtml}
                    ${metricsHtml}
                    <div class="mt-2 text-muted small">
                        <i class="fas fa-clock me-1"></i>
                        마지막 업데이트: ${new Date().toLocaleString()}
                        <span class="ms-3"><i class="fas fa-server me-1"></i>역할: ${server.role || 'Unknown'}</span>
                        <span class="ms-3"><i class="fas fa-hashtag me-1"></i>VMID: ${server.vmid || 'N/A'}</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    // 서버 문제점 생성 (실제 메트릭 기반)
    function generateServerIssues(server) {
        const issues = [];
        
        // 실제 메트릭 데이터가 있으면 사용
        if (server.metrics) {
            const metrics = server.metrics;
            
            // CPU 문제점
            if (metrics.cpu_usage > 90) {
                issues.push({
                    type: 'cpu',
                    level: 'critical',
                    message: `CPU 사용률이 90%를 초과하여 시스템이 불안정합니다.`,
                    value: metrics.cpu_usage.toFixed(1),
                    threshold: 90
                });
            } else if (metrics.cpu_usage > 80) {
                issues.push({
                    type: 'cpu',
                    level: 'warning',
                    message: `CPU 사용률이 80%를 초과하여 주의가 필요합니다.`,
                    value: metrics.cpu_usage.toFixed(1),
                    threshold: 80
                });
            }
            
            // 메모리 문제점
            if (metrics.memory_usage > 90) {
                issues.push({
                    type: 'memory',
                    level: 'critical',
                    message: `메모리 사용률이 90%를 초과하여 OOM 위험이 있습니다.`,
                    value: metrics.memory_usage.toFixed(1),
                    threshold: 90
                });
            } else if (metrics.memory_usage > 80) {
                issues.push({
                    type: 'memory',
                    level: 'warning',
                    message: `메모리 사용률이 80%를 초과하여 모니터링이 필요합니다.`,
                    value: metrics.memory_usage.toFixed(1),
                    threshold: 80
                });
            }
            
            // 디스크 문제점
            if (metrics.disk_usage > 90) {
                issues.push({
                    type: 'disk',
                    level: 'critical',
                    message: `디스크 사용률이 90%를 초과하여 공간 부족 위험이 있습니다.`,
                    value: metrics.disk_usage.toFixed(1),
                    threshold: 90
                });
            } else if (metrics.disk_usage > 80) {
                issues.push({
                    type: 'disk',
                    level: 'warning',
                    message: `디스크 사용률이 80%를 초과하여 주의가 필요합니다.`,
                    value: metrics.disk_usage.toFixed(1),
                    threshold: 80
                });
            }
            
            // 네트워크 문제점
            if (metrics.network_latency > 100) {
                issues.push({
                    type: 'network',
                    level: 'warning',
                    message: `네트워크 지연이 100ms를 초과하여 성능 저하가 발생할 수 있습니다.`,
                    value: metrics.network_latency.toFixed(1),
                    threshold: 100
                });
            }
        } else {
            // 메트릭 데이터가 없으면 기본 메시지
            if (server.status === 'critical') {
                issues.push({
                    type: 'system',
                    level: 'critical',
                    message: '시스템이 위험 상태입니다. 즉시 점검이 필요합니다.',
                    value: 'CRITICAL',
                    threshold: 'critical'
                });
            } else if (server.status === 'warning') {
                issues.push({
                    type: 'system',
                    level: 'warning',
                    message: '시스템에 주의가 필요한 상태가 감지되었습니다.',
                    value: 'WARNING',
                    threshold: 'warning'
                });
            }
        }
        
        return issues;
    }
    
    // 서버 메트릭 생성 (실제 API에서 가져오기)
    function generateServerMetrics(server) {
        // 실제 메트릭 데이터가 있으면 사용, 없으면 기본값
        if (server.metrics) {
            return {
                cpu_usage: server.metrics.cpu_usage,
                memory_usage: server.metrics.memory_usage,
                disk_usage: server.metrics.disk_usage,
                network_latency: server.metrics.network_latency
            };
        } else {
            // 기본값 반환
            return {
                cpu_usage: 0,
                memory_usage: 0,
                disk_usage: 0,
                network_latency: 0
            };
        }
    }
    
    // 이슈 타입별 아이콘 반환
    function getIssueIcon(type) {
        const icons = {
            'cpu': 'microchip',
            'memory': 'memory',
            'disk': 'hdd',
            'network': 'network-wired',
            'system': 'exclamation-triangle'
        };
        return icons[type] || 'exclamation-triangle';
    }
    
    // 이슈 타입별 단위 반환
    function getIssueUnit(type) {
        const units = {
            'cpu': '%',
            'memory': '%',
            'disk': '%',
            'network': 'ms',
            'system': ''
        };
        return units[type] || '';
    }
    
    // 서버 상세 정보 표시 (모달)
    window.showServerDetail = function(serverIp) {
        const server = servers.find(s => s.ip === serverIp);
        if (!server) {
            alert('서버 정보를 찾을 수 없습니다.');
            return;
        }
        
        // 실제 서버 정보만 표시
        let detailMessage = `서버: ${server.name} (${server.ip})\n`;
        detailMessage += `상태: ${server.status}\n`;
        detailMessage += `역할: ${server.role || 'Unknown'}\n`;
        detailMessage += `VMID: ${server.vmid || 'N/A'}\n\n`;
        
        if (server.status === 'critical') {
            detailMessage += '⚠️ 위험 상태: 시스템이 위험 상태입니다. 즉시 점검이 필요합니다.\n';
        } else if (server.status === 'warning') {
            detailMessage += '⚠️ 경고 상태: 시스템에 주의가 필요한 상태가 감지되었습니다.\n';
        }
        
        detailMessage += `\n📊 현재 상태: ${server.status === 'critical' ? '위험' : server.status === 'warning' ? '경고' : '정상'}\n`;
        detailMessage += `🔗 상세 메트릭은 Grafana 대시보드에서 확인하세요.`;
        
        alert(detailMessage);
    };
    
    // 서버 알림 새로고침 (스마트 새로고침 사용)
    window.refreshServerAlerts = function() {
        console.log('🔄 서버 알림 새로고침');
        forceRefresh();
    };
    
    // 데이터 새로고침 (스마트 새로고침 사용)
    function refreshData() {
        console.log('🔄 수동 새로고침 요청');
        forceRefresh();
    }
});
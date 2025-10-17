// storage.js
$(function() {
  console.log('[storage.js] storage.js loaded');
  
  // 숫자 포맷팅 함수 (index.html에서 가져옴)
  function format2f(val) {
    if (isNaN(val) || !isFinite(val)) return "0.00";
    return Number(val).toFixed(2);
  }
  function loadStorageInfo() {
    console.log('[storage.js] loadStorageInfo 호출');
    
    // 로딩 상태 표시
    $('#storage-table').html('<div class="text-center text-muted py-5"><i class="fas fa-spinner fa-spin fa-3x mb-3"></i><br>스토리지 정보를 불러오는 중...</div>');
    
    // 실제 API 연동
    $.get('/proxmox_storage', function(res) {
      const storages = res.storages || [];
      let html = '';
      
      if (storages.length === 0) {
        html = '<div class="text-center text-muted py-5"><i class="fas fa-hdd fa-3x mb-3"></i><br>등록된 스토리지가 없습니다.</div>';
      } else {
        html = '<div class="row">';
        storages.forEach(function(s) {
          const usedPercent = s.total > 0 ? Math.round((s.used / s.total) * 100) : 0;
          const totalGB = format2f(s.total / 1024 / 1024 / 1024);
          const availableGB = format2f((s.total - s.used) / 1024 / 1024 / 1024);
          const storageType = (s.type === 'lvmthin' || s.type === 'lvm' || s.storage === 'local' || s.storage === 'local-lvm') ? 'HDD' : (s.type === 'dir' ? 'SSD' : s.type);
          
          // 사용률에 따른 색상 결정
          let progressColor = '#28a745'; // 녹색 (0-60%)
          if (usedPercent > 80) {
            progressColor = '#dc3545'; // 빨간색 (80%+)
          } else if (usedPercent > 60) {
            progressColor = '#ffc107'; // 노란색 (60-80%)
          }
          
          html += `
            <div class="col-md-6 col-lg-4 mb-4">
              <div class="card h-100 border-0 shadow-sm">
                <div class="card-body text-center p-4">
                  <div class="position-relative d-inline-block mb-3">
                    <svg width="120" height="120" class="mb-2">
                      <circle cx="60" cy="60" r="50" fill="none" stroke="#e9ecef" stroke-width="8"/>
                      <circle cx="60" cy="60" r="50" fill="none" stroke="${progressColor}" stroke-width="8" 
                              stroke-dasharray="${2 * Math.PI * 50}" 
                              stroke-dashoffset="${2 * Math.PI * 50 * (1 - usedPercent/100)}"
                              transform="rotate(-90 60 60)"/>
                    </svg>
                    <div class="position-absolute top-50 start-50 translate-middle">
                      <div class="fw-bold fs-4">${usedPercent}%</div>
                      <small class="text-muted">사용중</small>
                    </div>
                  </div>
                  <h5 class="card-title mb-2">${s.storage}</h5>
                  <span class="badge bg-primary mb-3">${storageType}</span>
                  <div class="row text-center">
                    <div class="col-6">
                      <small class="text-muted d-block">총 용량</small>
                      <div class="fw-bold">${totalGB} GB</div>
                    </div>
                    <div class="col-6">
                      <small class="text-muted d-block">사용 가능</small>
                      <div class="fw-bold">${availableGB} GB</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>`;
        });
        html += '</div>';
      }
      
      $('#storage-table').html(html);
      console.log('[storage.js] 스토리지 테이블 렌더링 완료');
    }).fail(function(xhr) {
      console.error('[storage.js] 스토리지 정보 로드 실패:', xhr);
      $('#storage-table').html('<div class="text-center text-danger py-5"><i class="fas fa-exclamation-triangle fa-3x mb-3"></i><br>스토리지 정보를 불러오지 못했습니다.</div>');
    });
  }
  loadStorageInfo();
  $('#storage-refresh-btn').on('click', function() {
    console.log('[storage.js] #storage-refresh-btn 클릭');
    loadStorageInfo();
  });

  
}); 
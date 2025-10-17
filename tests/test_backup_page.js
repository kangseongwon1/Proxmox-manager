// 백업 관리 페이지 테스트
console.log('🔧 백업 관리 페이지 테스트 시작');

// 1. 페이지 로드 시뮬레이션
function testBackupPageLoad() {
  console.log('1️⃣ 백업 페이지 로드 테스트');
  
  // loadSPA 함수 호출 시뮬레이션
  if (typeof loadSPA === 'function') {
    loadSPA('/backups/content', '/static/backups.js');
  } else {
    console.log('❌ loadSPA 함수를 찾을 수 없음');
  }
}

// 2. API 호출 테스트
function testBackupAPI() {
  console.log('2️⃣ 백업 API 호출 테스트');
  
  fetch('/api/backups/nodes')
    .then(response => response.json())
    .then(data => {
      console.log('✅ 백업 API 응답:', data);
      if (data.success) {
        console.log(`📊 백업 개수: ${data.data?.backups?.length || 0}개`);
      } else {
        console.log('❌ 백업 API 실패:', data.message);
      }
    })
    .catch(error => {
      console.error('❌ 백업 API 오류:', error);
    });
}

// 3. 스크립트 로드 테스트
function testScriptLoad() {
  console.log('3️⃣ 스크립트 로드 테스트');
  
  // jQuery getScript 시뮬레이션
  if (typeof $ !== 'undefined') {
    $.getScript('/static/backups.js')
      .done(function() {
        console.log('✅ backups.js 로드 완료');
        if (typeof loadBackups === 'function') {
          console.log('✅ loadBackups 함수 발견');
          loadBackups();
        } else {
          console.log('❌ loadBackups 함수를 찾을 수 없음');
        }
      })
      .fail(function() {
        console.error('❌ backups.js 로드 실패');
      });
  } else {
    console.log('❌ jQuery를 찾을 수 없음');
  }
}

// 테스트 실행
setTimeout(() => {
  testBackupPageLoad();
  setTimeout(() => {
    testBackupAPI();
    setTimeout(() => {
      testScriptLoad();
    }, 1000);
  }, 1000);
}, 500);

console.log('🔧 백업 관리 페이지 테스트 준비 완료'); 
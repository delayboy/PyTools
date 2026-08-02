/**
 * 数智办公自动登录脚本
 * 需要先在 autox.js 里开启【无障碍服务】
 */

// 按控件中心点绝对坐标点击（等价于 Python 框架的 get_rect().get_middle() → device.click）
function clickCenter(field) {
    let b = field.bounds();
    log("点击坐标", b.centerX(), b.centerY());
    click(b.centerX(), b.centerY());
}

// 清空+输入：用 UiObject.setText() 只对该控件发 ACTION_SET_TEXT，先清空再写入
// 注意：全局 setText(text) 会广播到窗口所有 editable（editable(-1) 通配），不能用
// 必须用控件自己的 setText，且 field 必须是真正的 EditText，不能是外层 layout
function clearAndInput(field, input_str) {
    clickCenter(field);  // 聚焦输入框
    sleep(300);
    field.setText(input_str);  // 只替换该控件文本，不波及其他 EditText
    sleep(500);
}

auto.waitFor();
console.show();

// === Step 1: 检查数智办公是否已在屏幕上，不在则打开后台视图 ===
let szbg = text("数智办公").findOne(1000);
if (!szbg) {
    log("数智办公不在前台，打开后台视图");
    recents();
    sleep(1000);  // 等待后台视图动画
    szbg = text("数智办公").findOne(1000);
    if (!szbg) {
        // 向上滑动，翻找后台应用
        swipe(device.width / 2, device.height * 0.7, device.width / 2, device.height * 0.3, 500);
        sleep(1000);
    }
} else {
    log("数智办公已在前台");
}

// === Step 2: 找到数智办公并点击 ===
szbg = text("数智办公").findOne(3000);
if (!szbg) {
    log("错误：未找到数智办公");
    toast("未找到数智办公");
    exit();
}
clickCenter(szbg);
sleep(2000);

// === Step 3: 找到密码输入框并输入密码 ===
// 注意：密码框"请输入密码"是 hint，AutoX.js 的 text() 读 getText() 匹配不到 hint，
// uiautomator2 的 XML dump 会把空 EditText 的 hint 填到 text 属性里（Python 那边能搜到），
// 但 AutoX.js 不行，且无 hint() 选择器，也无 xpath()，所以改用 resource-id 精确定位
// 注意：密码框的 getText() 还被 UiObject 强制返回空（isPassword == true），双重失败
let usrField = id("cn.chinatelecom.ctdi.ywxt:id/login_ed_username").findOne(8000);
if (usrField) {
    // 已有手机号就不重复填充，避免覆盖用户手动输入的号码
    if (usrField.text().indexOf("137") === -1) {
        clearAndInput(usrField, "我的手机号");
    } else {
        log("手机号已存在，跳过填充");
    }
}

let pwdField = id("cn.chinatelecom.ctdi.ywxt:id/login_ed_password").findOne(8000);
if (!pwdField) {
    log("错误：未找到密码输入框");
    toast("未找到密码输入框");
    exit();
}
// password 属性为 true 时密码被掩码，点击 hide 控件切换为明文（password=false）
if (pwdField.password()) {
    let hide = id("cn.chinatelecom.ctdi.ywxt:id/login_hide_password").findOne(3000);
    if (hide) {
        clickCenter(hide);
        sleep(300);
    } else {
        log("警告：未找到密码显示切换按钮");
    }
}
clearAndInput(pwdField, "我的密码");

log("登录流程完成");
toast("数智办公登录流程已执行");

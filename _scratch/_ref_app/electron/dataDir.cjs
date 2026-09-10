�存档目录的落点决策（从 main.cjs 抽出，便于不起 Electron 直接跑测试）。
//
// Windows 上「文档」由注册表 User Shell Folders\Personal 指定，app.getPath("documents")
// 只把那条账面地址读出来返回：既不校验目标可用、也不创建。玩家把用户目录搬过盘、
// 重装系统、拔了移动硬盘之后，那条地址常常落在一个**悬空的联接（junction/symlink）**上：
// 名字在、属性写着目录，指向的目标却没了。
// 表现就是 mkdir 那一层被 exist_ok 吞掉、往里建子目录却 ENOENT/WinError 2（后端当场崩在
// 启动期，玩家连游戏都进不去）。
//
// 这里的次序是：探针 → 就地修（只把悬空联接的目标建出来）→ 再探 → 还不行才换地方。
// **绝不删/改玩家自己设的重定向**——那是他的系统设置，删了等于把他的「文档」拆了。

const fs = require("fs");
const path = require("path");

const FOLDER_NAME = "MingSalvageSim";
const noop = () => {};

// 目录能建、且真能往里写一个文件才算数。只看 existsSync/mkdirSync 不够：悬空联接
// 那一层 mkdirSync 不报错（recursive 遇到同名直接放过），坑留到写文件时才爆。
const dirIsWritable = (dir, warn = noop) => {
  const probe = path.join(dir, `.write_probe_${process.pid}`);
  try {
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(probe, "");
    return true;
  } catch (err) {
    warn(`数据目录不可写：${dir}（${err && err.message}）`);
    return false;
  } finally {
    try { fs.unlinkSync(probe); } catch {}
  }
};

// 沿路径往上找第一个"已经存在"的组件：若它是指向不存在目标的联接/符号链接，就把**目标**
// 建出来（联接本身原样不动，修完整条路径自然通）。修了返回 true，值得重探一次。
// 修不了的（目标所在的卷不在、没权限、那一层是个文件）返回 false，交给调用方换地方。
const repairDanglingRedirect = (dir, log = noop, warn = noop) => {
  let cur = path.resolve(dir);
  for (;;) {
    let info = null;
    try {
      info = fs.lstatSync(cur);
    } catch {
      // 这一层压根不存在 → 普通的"目录还没建"，mkdirSync(recursive) 自己能搞定，
      // 不需要修；继续往上看有没有坏掉的重定向。
      const up = path.dirname(cur);
      if (up === cur) return false;
      cur = up;
      continue;
    }
    if (info.isSymbolicLink()) {
      let target = "";
      try {
        target = path.resolve(path.dirname(cur), fs.readlinkSync(cur));
      } catch (err) {
        warn(`读不出重定向目标：${cur}（${err && err.message}）`);
        return false;
      }
      if (!fs.existsSync(target)) {
        try {
          fs.mkdirSync(target, { recursive: true });
        } catch (err) {
          warn(`重定向目标建不出来：${cur} → ${target}（${err && err.message}）`);
          return false;
        }
        log(`修复悬空重定向：${cur} → ${target}（目标不存在，已按原指向建出）`);
        return true;
      }
      // 联接是好的，接着往上看
    } else if (!info.isDirectory()) {
      warn(`路径被同名文件占住，无法建目录：${cur}`);
      return false;
    } else {
      return false; // 撞到真目录：这条路径上没有坏掉的重定向，没什么可修
    }
    const up = path.dirname(cur);
    if (up === cur) return false;
    cur = up;
  }
};

// 落点决策。Windows 存档只认「文档\\MingSalvageSim」这一个落点：探不通、修不好就**抛错**
// （splash 会原样展示 message），绝不静默换到 userData——换了等于玩家眼里「存档全没了」，
// 本节新档还落在另一处、Steam 云（按文档目录配的）也收不到，比启动报错伤得多（20260826 定）。
const pickGameDataDir = ({ platform, documentsDir, userDataDir, log = noop, warn = noop }) => {
  if (platform !== "win32") return userDataDir;
  if (!documentsDir) {
    throw new Error(
      "取不到系统的「文档」文件夹路径，游戏存档无处安放。" +
      "请检查系统的「文档」文件夹设置（注册表 User Shell Folders）后再启动。",
    );
  }
  const dir = path.join(documentsDir, FOLDER_NAME);
  let ok = dirIsWritable(dir, warn);
  for (let round = 0; !ok && round < 3; round++) {
    if (!repairDanglingRedirect(dir, log, warn)) break;
    ok = dirIsWritable(dir, warn);
    if (ok) log(`「文档」目录已修好，存档仍放 ${dir}`);
  }
  if (ok) return dir;
  throw new Error(
    `存档目录不可用：${dir}。` +
    "请检查「文档」文件夹：若被迁移到已拔出/已不存在的磁盘，请恢复该磁盘，" +
    "或右键「文档」→属性→位置，把它改回可用的路径；也请确认没有杀毒软件拦着写入。" +
    "修好后再启动游戏，存档不会自动搬去别的目录。",
  );
};

module.exports = { FOLDER_NAME, dirIsWritable, repairDanglingRedirect, pickGameDataDir };
{"steam"
const { app, BrowserWindow } = require('electron')
const path = require('path')
const { spawn } = require('child_process')

let mainWindow;
let pythonProcess;

function createWindow() {
  // 创建浏览器窗口
  mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    }
  })

  mainWindow.loadFile('dist/index.html')

  // 打开开发者工具
  mainWindow.webContents.openDevTools()

  // 监听窗口关闭事件
  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

app.on('ready', function () {
  createWindow();
  console.log('ready');

    // 打印python可执行文件路径
    const pythonExePath = path.join(__dirname, 'dist', 'serialAPI.exe')
    console.log(pythonExePath)

  // 启动python可执行文件
  pythonProcess = spawn(pythonExePath, [], {
    cwd: path.join(__dirname, 'dist') // 设置工作目录为dist
  })

  // 监听python输出
  pythonProcess.stdout.on('data', (data) => {
    console.log('Python stdout: ' + data.toString())
  })

  // 监听python错误
  pythonProcess.stderr.on('data', (data) => {
    console.error('Python stderr: ' + data.toString())
  })

  // 监听python关闭
  pythonProcess.on('close', (code) => {
    console.log('Python close: ' + code)
  })

  // 监听应用程序关闭事件，确保python进程关闭
  app.on('before-quit', () => {
    pythonProcess.kill()
  })
})

// 当全部窗口关闭时退出
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('activate', () => {
//   if (mainWindow === null) {
//     createWindow()
//   }
})




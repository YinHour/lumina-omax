'use client'

import { useState, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Image from 'next/image'
import { useAuth } from '@/lib/hooks/use-auth'
import { useAuthStore } from '@/lib/stores/auth-store'
import { getConfig } from '@/lib/config'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { 
  AlertCircle, 
  Beaker, 
  ShieldCheck, 
  Zap, 
  Activity, 
  Layers, 
  CheckCircle2, 
  LogIn, 
  UserPlus,
  ArrowRight,
  Award
} from 'lucide-react'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { useTranslation } from '@/lib/hooks/use-translation'

export function LoginForm() {
  const { t, language } = useTranslation()
  const router = useRouter()
  const searchParams = useSearchParams()
  
  // Save redirect URL from middleware into sessionStorage
  useEffect(() => {
    const redirect = searchParams?.get('redirect')
    if (redirect) {
      sessionStorage.setItem('redirectAfterLogin', redirect)
    }
  }, [searchParams])
  
  // Auth Store states & actions
  const { authRequired, checkAuthRequired, hasHydrated, isAuthenticated } = useAuthStore()
  const { login, register, isLoading, error } = useAuth()
  
  // Local UI States
  const [isCheckingAuth, setIsCheckingAuth] = useState(true)
  const [activeTab, setActiveTab] = useState<'login' | 'register'>('login')
  const [configInfo, setConfigInfo] = useState<{ apiUrl: string; version: string; buildTime: string } | null>(null)
  
  // Login fields
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  
  // Registration fields
  const [regUsername, setRegUsername] = useState('')
  const [regDisplayName, setRegDisplayName] = useState('')
  const [regPassword, setRegPassword] = useState('')
  const [regConfirmPassword, setRegConfirmPassword] = useState('')
  const [registrationSuccess, setRegistrationSuccess] = useState<string | null>(null)
  const [registrationError, setRegistrationError] = useState<string | null>(null)
  const [isRegistering, setIsRegistering] = useState(false)

  // Load config info for debugging
  useEffect(() => {
    getConfig().then(cfg => {
      setConfigInfo({
        apiUrl: cfg.apiUrl,
        version: cfg.version,
        buildTime: cfg.buildTime,
      })
    }).catch(err => {
      console.error('Failed to load config:', err)
    })
  }, [])

  // Check if authentication is required on mount
  useEffect(() => {
    if (!hasHydrated) {
      return
    }

    const checkAuth = async () => {
      try {
        const required = await checkAuthRequired()

        // If auth is not required, redirect to notebooks
        if (!required) {
          router.push('/notebooks')
        }
      } catch (error) {
        console.error('Error checking auth requirement:', error)
        // On error, assume auth is required to be safe
      } finally {
        setIsCheckingAuth(false)
      }
    }

    // If we already know auth status, use it
    if (authRequired !== null) {
      if (!authRequired && isAuthenticated) {
        router.push('/notebooks')
      } else {
        setIsCheckingAuth(false)
      }
    } else {
      void checkAuth()
    }
  }, [hasHydrated, authRequired, checkAuthRequired, router, isAuthenticated])

  // Show loading while checking if auth is required
  if (!hasHydrated || isCheckingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <LoadingSpinner />
      </div>
    )
  }

  // If we still don't know if auth is required (connection error), show error
  if (authRequired === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle>{t.common.connectionError}</CardTitle>
            <CardDescription>
              {t.common.unableToConnect}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-start gap-2 text-red-600 text-sm">
                <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                <div className="flex-1">
                  {error || t.auth.connectErrorHint}
                </div>
              </div>

              {configInfo && (
                <div className="space-y-2 text-xs text-muted-foreground border-t pt-3">
                  <div className="font-medium">{t.common.diagnosticInfo}:</div>
                  <div className="space-y-1 font-mono">
                    <div>{t.common.version}: {configInfo.version}</div>
                    <div>{t.common.built}: {new Date(configInfo.buildTime).toLocaleString(language === 'zh-CN' ? 'zh-CN' : language === 'zh-TW' ? 'zh-TW' : 'en-US')}</div>
                    <div className="break-all">{t.common.apiUrl}: {configInfo.apiUrl}</div>
                    <div className="break-all">{t.common.frontendUrl}: {typeof window !== 'undefined' ? window.location.href : 'N/A'}</div>
                  </div>
                  <div className="text-xs pt-2">
                    {t.common.checkConsoleLogs}
                  </div>
                </div>
              )}

              <Button
                onClick={() => window.location.reload()}
                className="w-full"
              >
                {t.common.retryConnection}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Handle Login submission
  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!password.trim()) return
    const loginUser = username.trim() || 'admin'
    try {
      await login(loginUser, password)
    } catch (error) {
      console.error('Unhandled error during login:', error)
    }
  }

  // Handle Registration submission
  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setRegistrationSuccess(null)
    setRegistrationError(null)

    if (!regUsername.trim() || !regPassword.trim() || !regDisplayName.trim()) {
      setRegistrationError('所有字段均为必填项')
      return
    }

    if (regPassword !== regConfirmPassword) {
      setRegistrationError('两次输入的密码不一致')
      return
    }

    setIsRegistering(true)
    try {
      const res = await register(regUsername, regPassword, regDisplayName)
      if (res.success) {
        setRegistrationSuccess('注册申请已成功提交！您的账号当前处于待审批 (pending) 状态。请联系管理员激活账号后进行登录。')
        setRegUsername('')
        setRegDisplayName('')
        setRegPassword('')
        setRegConfirmPassword('')
      } else {
        setRegistrationError(res.message || '注册失败，请稍后重试')
      }
    } catch {
      setRegistrationError('网络连接失败，请检查后端服务')
    } finally {
      setIsRegistering(false)
    }
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-12 bg-background select-none text-foreground">
      {/* Left Column: Methodology & Enablement Panel */}
      <div className="hidden lg:flex lg:col-span-7 bg-gradient-to-br from-slate-950 via-slate-900 to-teal-950 p-12 flex-col justify-between border-r border-border relative overflow-hidden">
        {/* Decorative Grid and Gradients */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px] pointer-events-none" />
        <div className="absolute top-1/4 -left-20 w-96 h-96 bg-teal-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-1/4 -right-20 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* Logo and Brand */}
        <div className="flex items-center gap-3.5 relative z-10">
          <Image src="/logo.png" alt="Lumiton Omax Logo" width={40} height={40} className="h-10 w-auto select-none pointer-events-none" />
          <div>
            <div className="font-bold text-xl tracking-wide bg-clip-text text-transparent bg-gradient-to-r from-teal-400 to-indigo-400">
              Lumiton·Omax | 知涌
            </div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-widest">
              Oilfield Chemistry R&D Platform
            </div>
          </div>
        </div>

        {/* Methodology Core Concept Showcase */}
        <div className="my-auto space-y-8 relative z-10 max-w-2xl">
          <div className="space-y-4">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-teal-500/10 text-teal-400 border border-teal-500/20">
              <Zap className="h-3.5 w-3.5" /> 核心研发方法学变革
            </span>
            <h1 className="text-3xl font-extrabold tracking-tight leading-tight lg:text-4xl text-white">
              配方-工况-性能映射系统
            </h1>
            <p className="text-muted-foreground text-sm leading-relaxed max-w-xl">
              将历史经验、实验数据、现场反馈和产品机理假设组织成可追踪、可复盘、可预测的研发决策系统——让 AI 进入清晰科研链路，而非替代研发判断。
            </p>
          </div>

          {/* 7-Phase Research Loop Steps */}
          <div className="grid grid-cols-2 gap-5 pt-2">
            <div className="p-4 rounded-xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] transition-colors space-y-2">
              <div className="flex items-center gap-2 text-teal-400 text-sm font-semibold">
                <Layers className="h-4 w-4" /> 7步研发闭环 (Loop)
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                产品代号→配方版本→原料批次→水泥批次→工况条件→性能结果→失败归因，标准数字化链路，让每一轮实验都有据可循。
              </p>
            </div>

            <div className="p-4 rounded-xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] transition-colors space-y-2">
              <div className="flex items-center gap-2 text-indigo-400 text-sm font-semibold">
                <Beaker className="h-4 w-4" /> 原料与配方映射
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                追踪降失水剂分子理化特性在水泥矿物相变中的微观作用，分析配方与水泥批次波动的微观作用机制。
              </p>
            </div>

            <div className="p-4 rounded-xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] transition-colors space-y-2">
              <div className="flex items-center gap-2 text-teal-400 text-sm font-semibold">
                <ShieldCheck className="h-4 w-4" /> 失败用例沉淀
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                自动抓取配方、工艺、测试条件、失效现象与改进方向，将不可复用的个人经验转化为团队共享的结构化研发资产。
              </p>
            </div>

            <div className="p-4 rounded-xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] transition-colors space-y-2">
              <div className="flex items-center gap-2 text-indigo-400 text-sm font-semibold">
                <Activity className="h-4 w-4" /> 机理与预测并行
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                每次回答区分&ldquo;已有证据&rdquo;&ldquo;合理推断&rdquo;&ldquo;需验证假设&rdquo;，对新配方建议输出机理假设、实验验证路径和失败判据。
              </p>
            </div>
          </div>

          {/* Core Metrics */}
          <div className="flex gap-8 border-t border-white/5 pt-6">
            <div>
              <div className="text-2xl font-bold text-teal-400">+40%</div>
              <div className="text-xs text-muted-foreground">实验复用与沉淀率</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-indigo-400">-30%</div>
              <div className="text-xs text-muted-foreground">现场放大应用失效风险</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-teal-400">1/2</div>
              <div className="text-xs text-muted-foreground">极端工况筛选试错周期</div>
            </div>
          </div>

          {/* AI Capabilities */}
          <div className="grid grid-cols-3 gap-4 pt-2">
            <div className="text-center p-3 rounded-lg border border-white/5 bg-white/[0.01]">
              <div className="text-teal-400 text-lg font-bold">50+</div>
              <div className="text-[10px] text-muted-foreground mt-1">文件格式解析</div>
            </div>
            <div className="text-center p-3 rounded-lg border border-white/5 bg-white/[0.01]">
              <div className="text-teal-400 text-lg font-bold">多源</div>
              <div className="text-[10px] text-muted-foreground mt-1">语义向量检索</div>
            </div>
            <div className="text-center p-3 rounded-lg border border-white/5 bg-white/[0.01]">
              <div className="text-teal-400 text-lg font-bold">8+</div>
              <div className="text-[10px] text-muted-foreground mt-1">AI 大模型供应商</div>
            </div>
          </div>
        </div>

        {/* Footer Brand Info */}
        <div className="text-xs text-muted-foreground/60 flex justify-between items-center relative z-10">
          <div>© 2026 Lumiton·Omax | 知涌 联合研发实验室. All rights reserved.</div>
          <div className="flex items-center gap-1">
            <Award className="h-3 w-3 text-teal-400" />
            <span>智能石化 R&D 平台</span>
          </div>
        </div>
      </div>

      {/* Right Column: Auth Panel */}
      <div className="col-span-12 lg:col-span-5 flex items-center justify-center p-6 bg-slate-900/5 dark:bg-slate-950/20 select-none">
        <Card className="w-full max-w-[420px] shadow-xl border-border bg-card">
          <CardHeader className="text-center pb-4">
            <CardTitle className="text-2xl font-bold tracking-tight text-foreground">
              科研数据中台
            </CardTitle>
            <CardDescription className="text-muted-foreground text-xs mt-1">
              油井化学智能决策与文献大模型系统
            </CardDescription>
          </CardHeader>
          
          <CardContent className="space-y-4">
            <Tabs 
              value={activeTab} 
              onValueChange={(val) => {
                setActiveTab(val as 'login' | 'register')
                setRegistrationSuccess(null)
                setRegistrationError(null)
              }}
              className="w-full"
            >
              <TabsList className="grid grid-cols-2 w-full mb-4">
                <TabsTrigger value="login" className="flex items-center gap-1.5">
                  <LogIn className="h-4 w-4" /> 用户登录
                </TabsTrigger>
                <TabsTrigger value="register" className="flex items-center gap-1.5">
                  <UserPlus className="h-4 w-4" /> 申请注册
                </TabsTrigger>
              </TabsList>

              {/* Login Content */}
              <TabsContent value="login">
                <form onSubmit={handleLoginSubmit} className="space-y-4">
                  <div className="space-y-3">
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-muted-foreground">用户名 / 邮箱</label>
                      <Input
                        type="text"
                        placeholder="请输入您的用户名 (默认为 admin)"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        disabled={isLoading}
                        className="bg-muted/40"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-muted-foreground">密码</label>
                      <Input
                        type="password"
                        placeholder={t.auth.passwordPlaceholder}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        disabled={isLoading}
                        className="bg-muted/40"
                      />
                    </div>
                  </div>

                  {error && (
                    <div className="flex items-start gap-2 text-red-500 text-xs bg-red-500/10 p-2.5 rounded-lg border border-red-500/20">
                      <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                      <div>{error}</div>
                    </div>
                  )}

                  <Button
                    type="submit"
                    className="w-full mt-2"
                    disabled={isLoading || !password.trim()}
                  >
                    {isLoading ? (
                      <span className="flex items-center gap-2">
                        <LoadingSpinner className="h-4 w-4" /> 正在进入系统...
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5 justify-center">
                        进入科研平台 <ArrowRight className="h-4 w-4" />
                      </span>
                    )}
                  </Button>

                  <div className="text-[11px] text-center text-muted-foreground mt-2 border-t pt-3 bg-muted/20 p-2 rounded border">
                    Lumiton·Omax 科研数据中台
                  </div>
                </form>
              </TabsContent>

              {/* Register Content */}
              <TabsContent value="register">
                <form onSubmit={handleRegisterSubmit} className="space-y-4">
                  <div className="space-y-3">
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-muted-foreground">申请登录用户名</label>
                      <Input
                        type="text"
                        placeholder="例：zhangsan"
                        value={regUsername}
                        onChange={(e) => setRegUsername(e.target.value)}
                        disabled={isRegistering}
                        className="bg-muted/40"
                        required
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-muted-foreground">真实姓名 / 科研昵称</label>
                      <Input
                        type="text"
                        placeholder="例：张三 (水泥工程组)"
                        value={regDisplayName}
                        onChange={(e) => setRegDisplayName(e.target.value)}
                        disabled={isRegistering}
                        className="bg-muted/40"
                        required
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-muted-foreground">设置平台密码</label>
                      <Input
                        type="password"
                        placeholder="请输入强密码"
                        value={regPassword}
                        onChange={(e) => setRegPassword(e.target.value)}
                        disabled={isRegistering}
                        className="bg-muted/40"
                        required
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-muted-foreground">确认密码</label>
                      <Input
                        type="password"
                        placeholder="请再次输入密码"
                        value={regConfirmPassword}
                        onChange={(e) => setRegConfirmPassword(e.target.value)}
                        disabled={isRegistering}
                        className="bg-muted/40"
                        required
                      />
                    </div>
                  </div>

                  {registrationError && (
                    <div className="flex items-start gap-2 text-red-500 text-xs bg-red-500/10 p-2.5 rounded-lg border border-red-500/20">
                      <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                      <div>{registrationError}</div>
                    </div>
                  )}

                  {registrationSuccess && (
                    <div className="flex items-start gap-2 text-teal-600 text-xs bg-teal-500/10 p-3 rounded-lg border border-teal-500/20 leading-relaxed">
                      <CheckCircle2 className="h-5 w-5 mt-0.5 flex-shrink-0 text-teal-500" />
                      <div>{registrationSuccess}</div>
                    </div>
                  )}

                  <Button
                    type="submit"
                    className="w-full mt-2"
                    disabled={isRegistering || registrationSuccess !== null}
                  >
                    {isRegistering ? (
                      <span className="flex items-center gap-2">
                        <LoadingSpinner className="h-4 w-4" /> 正在提交申请...
                      </span>
                    ) : (
                      '提交注册申请'
                    )}
                  </Button>

                  <div className="text-[10px] text-center text-muted-foreground leading-relaxed">
                    ℹ️ 提示：注册后需要具有 admin 权限的管理员在“系统设置 &rarr; 成员审批”中批准激活，方可正式登录使用。
                  </div>
                </form>
              </TabsContent>
            </Tabs>

            {configInfo && (
              <div className="text-[10px] text-center text-muted-foreground/60 pt-2 border-t mt-4">
                <div>平台版本：v{configInfo.version}</div>
                <div className="font-mono text-[9px] mt-0.5">{configInfo.apiUrl}</div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

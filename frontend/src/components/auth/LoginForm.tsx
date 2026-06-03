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
      setRegistrationError(t.auth.regAllFieldsRequired)
      return
    }

    if (regPassword !== regConfirmPassword) {
      setRegistrationError(t.auth.regPasswordMismatch)
      return
    }

    setIsRegistering(true)
    try {
      const res = await register(regUsername, regPassword, regDisplayName)
      if (res.success) {
        setRegistrationSuccess(t.auth.regSuccess)
        setRegUsername('')
        setRegDisplayName('')
        setRegPassword('')
        setRegConfirmPassword('')
      } else {
        setRegistrationError(res.message || t.auth.regFailed)
      }
    } catch {
      setRegistrationError(t.auth.regNetworkError)
    } finally {
      setIsRegistering(false)
    }
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-12 bg-background select-none text-foreground">
      {/* Left Column: Methodology & Enablement Panel */}
      <div className="hidden lg:flex lg:col-span-7 bg-gradient-to-br from-slate-50 via-white to-teal-50 dark:from-slate-950 dark:via-slate-900 dark:to-teal-950 p-6 lg:p-10 3xl:p-12 flex-col justify-between border-r border-border relative overflow-hidden">
        {/* Decorative Grid and Gradients */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px] lg:bg-[size:32px_32px] 3xl:bg-[size:40px_40px] pointer-events-none" />
        <div className="absolute top-1/4 -left-20 w-96 h-96 3xl:w-[600px] 3xl:h-[600px] bg-teal-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-1/4 -right-20 w-96 h-96 3xl:w-[600px] 3xl:h-[600px] bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* Logo and Brand */}
        <div className="flex items-center gap-3.5 relative z-10">
          <Image src="/logo.png" alt="Lumiton Omax Logo" width={56} height={56} className="h-10 lg:h-12 3xl:h-14 w-auto select-none pointer-events-none" />
          <div>
            <div className="font-bold text-xl lg:text-2xl 3xl:text-3xl tracking-wide bg-clip-text text-transparent bg-gradient-to-r from-teal-600 to-indigo-600 dark:from-teal-400 dark:to-indigo-400">
              Lumiton·Omax | 知涌
            </div>
            <div className="text-[10px] lg:text-xs 3xl:text-sm text-muted-foreground uppercase tracking-widest">
              Oilfield Chemistry R&D Platform
            </div>
          </div>
        </div>

        {/* Methodology Core Concept Showcase */}
        <div className="my-auto space-y-4 lg:space-y-6 3xl:space-y-8 relative z-10 max-w-2xl 3xl:max-w-4xl mx-auto">
          <div className="space-y-2 lg:space-y-3 3xl:space-y-4">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs lg:text-sm 3xl:text-base font-medium bg-teal-500/10 text-teal-600 dark:text-teal-400 border border-teal-500/20">
              <Zap className="h-3.5 w-3.5 lg:h-4 lg:w-4 3xl:h-5 3xl:w-5" /> 核心研发方法学变革
            </span>
            <h1 className="text-3xl font-extrabold tracking-tight leading-tight lg:text-4xl 3xl:text-5xl text-slate-900 dark:text-white">
              配方-工况-性能映射系统
            </h1>
            <p className="text-muted-foreground text-sm lg:text-base 3xl:text-lg leading-relaxed max-w-xl 3xl:max-w-2xl">
              将历史经验、实验数据、现场反馈和产品机理假设组织成可追踪、可复盘、可预测的研发决策系统——让 AI 进入清晰科研链路，而非替代研发判断。
            </p>
          </div>

          {/* 7-Phase Research Loop Steps */}
          <div className="grid grid-cols-2 gap-3 lg:gap-4 3xl:gap-5 pt-2">
            <div className="p-3 lg:p-4 3xl:p-6 rounded-xl border border-slate-200 dark:border-white/5 bg-slate-100 dark:bg-white/[0.02] hover:bg-slate-200 dark:hover:bg-white/[0.04] transition-all duration-200 space-y-1.5 lg:space-y-2">
              <div className="flex items-center gap-2 text-teal-600 dark:text-teal-400 text-sm lg:text-base 3xl:text-lg font-semibold">
                <Layers className="h-4 w-4 lg:h-5 lg:w-5 3xl:h-6 3xl:w-6" /> 7步研发闭环 (Loop)
              </div>
              <p className="text-xs lg:text-sm 3xl:text-base text-muted-foreground leading-relaxed">
                产品代号→配方版本→原料批次→水泥批次→工况条件→性能结果→失败归因，标准数字化链路，让每一轮实验都有据可循。
              </p>
            </div>

            <div className="p-3 lg:p-4 3xl:p-6 rounded-xl border border-slate-200 dark:border-white/5 bg-slate-100 dark:bg-white/[0.02] hover:bg-slate-200 dark:hover:bg-white/[0.04] transition-all duration-200 space-y-1.5 lg:space-y-2">
              <div className="flex items-center gap-2 text-indigo-600 dark:text-indigo-400 text-sm lg:text-base 3xl:text-lg font-semibold">
                <Beaker className="h-4 w-4 lg:h-5 lg:w-5 3xl:h-6 3xl:w-6" /> 原料与配方映射
              </div>
              <p className="text-xs lg:text-sm 3xl:text-base text-muted-foreground leading-relaxed">
                追踪降失水剂分子理化特性在水泥矿物相变中的微观作用，分析配方与水泥批次波动的微观作用机制。
              </p>
            </div>

            <div className="p-3 lg:p-4 3xl:p-6 rounded-xl border border-slate-200 dark:border-white/5 bg-slate-100 dark:bg-white/[0.02] hover:bg-slate-200 dark:hover:bg-white/[0.04] transition-all duration-200 space-y-1.5 lg:space-y-2">
              <div className="flex items-center gap-2 text-teal-600 dark:text-teal-400 text-sm lg:text-base 3xl:text-lg font-semibold">
                <ShieldCheck className="h-4 w-4 lg:h-5 lg:w-5 3xl:h-6 3xl:w-6" /> 失败用例沉淀
              </div>
              <p className="text-xs lg:text-sm 3xl:text-base text-muted-foreground leading-relaxed">
                自动抓取配方、工艺、测试条件、失效现象与改进方向，将不可复用的个人经验转化为团队共享的结构化研发资产。
              </p>
            </div>

            <div className="p-3 lg:p-4 3xl:p-6 rounded-xl border border-slate-200 dark:border-white/5 bg-slate-100 dark:bg-white/[0.02] hover:bg-slate-200 dark:hover:bg-white/[0.04] transition-all duration-200 space-y-1.5 lg:space-y-2">
              <div className="flex items-center gap-2 text-indigo-600 dark:text-indigo-400 text-sm lg:text-base 3xl:text-lg font-semibold">
                <Activity className="h-4 w-4 lg:h-5 lg:w-5 3xl:h-6 3xl:w-6" /> 机理与预测并行
              </div>
              <p className="text-xs lg:text-sm 3xl:text-base text-muted-foreground leading-relaxed">
                每次回答区分&ldquo;已有证据&rdquo;&ldquo;合理推断&rdquo;&ldquo;需验证假设&rdquo;，对新配方建议输出机理假设、实验验证路径和失败判据。
              </p>
            </div>
          </div>

          {/* Core Metrics */}
          <div className="grid grid-cols-3 gap-2 lg:gap-3 3xl:gap-4 border-t border-border pt-4 lg:pt-5 3xl:pt-6">
            <div className="text-center">
              <div className="text-2xl lg:text-3xl 3xl:text-4xl font-bold text-teal-500 dark:text-teal-400">+40%</div>
              <div className="text-xs lg:text-sm 3xl:text-base text-muted-foreground">实验复用与沉淀率</div>
            </div>
            <div className="text-center">
              <div className="text-2xl lg:text-3xl 3xl:text-4xl font-bold text-indigo-500 dark:text-indigo-400">-30%</div>
              <div className="text-xs lg:text-sm 3xl:text-base text-muted-foreground">现场放大应用失效风险</div>
            </div>
            <div className="text-center">
              <div className="text-2xl lg:text-3xl 3xl:text-4xl font-bold text-teal-500 dark:text-teal-400">1/2</div>
              <div className="text-xs lg:text-sm 3xl:text-base text-muted-foreground">极端工况筛选试错周期</div>
            </div>
          </div>

          {/* AI Capabilities */}
          <div className="grid grid-cols-3 gap-2 lg:gap-3 3xl:gap-4 pt-2">
            <div className="text-center p-3 rounded-lg border border-slate-200 dark:border-white/5 bg-slate-100 dark:bg-white/[0.01]">
              <div className="text-teal-500 dark:text-teal-400 text-lg lg:text-xl 3xl:text-2xl font-bold">50+</div>
              <div className="text-[10px] lg:text-xs 3xl:text-sm text-muted-foreground mt-1">文件格式解析</div>
            </div>
            <div className="text-center p-3 rounded-lg border border-slate-200 dark:border-white/5 bg-slate-100 dark:bg-white/[0.01]">
              <div className="text-teal-500 dark:text-teal-400 text-lg lg:text-xl 3xl:text-2xl font-bold">多源</div>
              <div className="text-[10px] lg:text-xs 3xl:text-sm text-muted-foreground mt-1">语义向量检索</div>
            </div>
            <div className="text-center p-3 rounded-lg border border-slate-200 dark:border-white/5 bg-slate-100 dark:bg-white/[0.01]">
              <div className="text-teal-500 dark:text-teal-400 text-lg lg:text-xl 3xl:text-2xl font-bold">8+</div>
              <div className="text-[10px] lg:text-xs 3xl:text-sm text-muted-foreground mt-1">AI 大模型供应商</div>
            </div>
          </div>
        </div>

        {/* Footer Brand Info */}
        <div className="text-xs lg:text-sm 3xl:text-base text-muted-foreground/60 flex justify-between items-center relative z-10">
          <div>© 2026 Lumiton·Omax | 知涌 联合研发实验室. All rights reserved.</div>
          <div className="flex items-center gap-1">
            <Award className="h-3 w-3 lg:h-4 lg:w-4 3xl:h-5 3xl:w-5 text-teal-500 dark:text-teal-400" />
            <span>智能石化 R&D 平台</span>
          </div>
        </div>
      </div>

      {/* Right Column: Auth Panel */}
      <div className="col-span-12 lg:col-span-5 flex flex-col items-center justify-center gap-6 p-4 sm:p-6 lg:p-8 3xl:p-12 bg-slate-100/50 dark:bg-slate-950/20 select-none">
        {/* Mobile Brand Header */}
        <div className="lg:hidden flex items-center gap-3 pt-2">
          <Image src="/logo.png" alt="Logo" width={40} height={40} className="h-9 w-auto" />
          <div>
            <div className="font-bold text-lg bg-clip-text text-transparent bg-gradient-to-r from-teal-600 to-indigo-600 dark:from-teal-400 dark:to-indigo-400">
              Lumiton·Omax | 知涌
            </div>
            <div className="text-[10px] text-muted-foreground">Oilfield Chemistry R&D Platform</div>
          </div>
        </div>

        <Card className="w-full max-w-[420px] lg:max-w-[480px] 3xl:max-w-[540px] shadow-xl border-border bg-card transition-shadow hover:shadow-2xl">
          <CardHeader className="text-center pb-4">
            <CardTitle className="text-2xl lg:text-3xl 3xl:text-[34px] font-bold tracking-tight text-foreground">
              {t.auth.platformTitle}
            </CardTitle>
            <CardDescription className="text-muted-foreground text-xs lg:text-sm 3xl:text-base mt-1">
              {t.auth.platformDesc}
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
                <TabsTrigger value="login" className="flex items-center gap-1.5 text-sm lg:text-base 3xl:text-lg">
                  <LogIn className="h-4 w-4 lg:h-5 lg:w-5" /> {t.auth.tabLogin}
                </TabsTrigger>
                <TabsTrigger value="register" className="flex items-center gap-1.5 text-sm lg:text-base 3xl:text-lg">
                  <UserPlus className="h-4 w-4 lg:h-5 lg:w-5" /> {t.auth.tabRegister}
                </TabsTrigger>
              </TabsList>

              {/* Login Content */}
              <TabsContent value="login">
                <form onSubmit={handleLoginSubmit} className="space-y-4">
                  <div className="space-y-3">
                    <div className="space-y-1">
                      <label className="text-xs lg:text-sm 3xl:text-base font-semibold text-muted-foreground">{t.auth.usernameOrEmail}</label>
                      <Input
                        type="text"
                        placeholder={t.auth.usernamePlaceholder}
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        disabled={isLoading}
                        className="bg-muted/40 3xl:text-lg 3xl:py-3"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs lg:text-sm 3xl:text-base font-semibold text-muted-foreground">{t.auth.password}</label>
                      <Input
                        type="password"
                        placeholder={t.auth.passwordPlaceholder}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        disabled={isLoading}
                        className="bg-muted/40 3xl:text-lg 3xl:py-3"
                      />
                    </div>
                  </div>

                  {error && (
                    <div className="flex items-start gap-2 text-red-500 text-xs lg:text-sm 3xl:text-base bg-red-500/10 p-2.5 rounded-lg border border-red-500/20">
                      <AlertCircle className="h-4 w-4 lg:h-5 lg:w-5 mt-0.5 flex-shrink-0" />
                      <div>{error}</div>
                    </div>
                  )}

                  <Button
                    type="submit"
                    className="w-full mt-2 text-sm lg:text-base 3xl:text-lg 3xl:py-3"
                    disabled={isLoading || !password.trim()}
                  >
                    {isLoading ? (
                      <span className="flex items-center gap-2">
                        <LoadingSpinner className="h-4 w-4" /> {t.auth.signinLoading}
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5 justify-center">
                        {t.auth.enterPlatform} <ArrowRight className="h-4 w-4" />
                      </span>
                    )}
                  </Button>

                   <div className="text-[11px] lg:text-xs 3xl:text-sm text-center text-muted-foreground mt-2 border-t pt-3 bg-muted/20 p-2 rounded border">
                    {t.auth.platformTagline}
                  </div>
                </form>
              </TabsContent>

              {/* Register Content */}
              <TabsContent value="register">
                <form onSubmit={handleRegisterSubmit} className="space-y-4">
                  <div className="space-y-3">
                    <div className="space-y-1">
                      <label className="text-xs lg:text-sm 3xl:text-base font-semibold text-muted-foreground">{t.auth.regUsername}</label>
                      <Input
                        type="text"
                        placeholder={t.auth.regUsernamePlaceholder}
                        value={regUsername}
                        onChange={(e) => setRegUsername(e.target.value)}
                        disabled={isRegistering}
                        className="bg-muted/40 3xl:text-lg 3xl:py-3"
                        required
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs lg:text-sm 3xl:text-base font-semibold text-muted-foreground">{t.auth.regDisplayName}</label>
                      <Input
                        type="text"
                        placeholder={t.auth.regDisplayNamePlaceholder}
                        value={regDisplayName}
                        onChange={(e) => setRegDisplayName(e.target.value)}
                        disabled={isRegistering}
                        className="bg-muted/40 3xl:text-lg 3xl:py-3"
                        required
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs lg:text-sm 3xl:text-base font-semibold text-muted-foreground">{t.auth.regPassword}</label>
                      <Input
                        type="password"
                        placeholder={t.auth.regPasswordPlaceholder}
                        value={regPassword}
                        onChange={(e) => setRegPassword(e.target.value)}
                        disabled={isRegistering}
                        className="bg-muted/40 3xl:text-lg 3xl:py-3"
                        required
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs lg:text-sm 3xl:text-base font-semibold text-muted-foreground">{t.auth.regConfirmPassword}</label>
                      <Input
                        type="password"
                        placeholder={t.auth.regConfirmPasswordPlaceholder}
                        value={regConfirmPassword}
                        onChange={(e) => setRegConfirmPassword(e.target.value)}
                        disabled={isRegistering}
                        className="bg-muted/40 3xl:text-lg 3xl:py-3"
                        required
                      />
                    </div>
                  </div>

                  {registrationError && (
                    <div className="flex items-start gap-2 text-red-500 text-xs lg:text-sm 3xl:text-base bg-red-500/10 p-2.5 rounded-lg border border-red-500/20">
                      <AlertCircle className="h-4 w-4 lg:h-5 lg:w-5 mt-0.5 flex-shrink-0" />
                      <div>{registrationError}</div>
                    </div>
                  )}

                  {registrationSuccess && (
                    <div className="flex items-start gap-2 text-teal-600 text-xs lg:text-sm 3xl:text-base bg-teal-500/10 p-3 rounded-lg border border-teal-500/20 leading-relaxed">
                      <CheckCircle2 className="h-5 w-5 lg:h-6 lg:w-6 mt-0.5 flex-shrink-0 text-teal-500" />
                      <div>{registrationSuccess}</div>
                    </div>
                  )}

                  <Button
                    type="submit"
                    className="w-full mt-2 text-sm lg:text-base 3xl:text-lg 3xl:py-3"
                    disabled={isRegistering || registrationSuccess !== null}
                  >
                    {isRegistering ? (
                      <span className="flex items-center gap-2">
                        <LoadingSpinner className="h-4 w-4" /> {t.auth.regSubmitting}
                      </span>
                    ) : (
                      t.auth.regSubmit
                    )}
                  </Button>

                  <div className="text-[10px] lg:text-xs 3xl:text-sm text-center text-muted-foreground leading-relaxed">
                    {t.auth.regApprovalHint}
                  </div>
                </form>
              </TabsContent>
            </Tabs>

            {configInfo && (
              <div className="text-[10px] lg:text-xs 3xl:text-sm text-center text-muted-foreground/60 pt-2 border-t mt-4">
                <div>{t.auth.configVersion}{configInfo.version}</div>
                <div className="font-mono text-[9px] lg:text-[10px] 3xl:text-xs mt-0.5">{configInfo.apiUrl}</div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { ArrowLeft, ScanLine, Send, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { api, errorMessage } from '@/api/client'
import type { OtpRequestResult, TokenPair } from '@/api/types'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/hooks/useAuth'

/**
 * Admin panelga kirish — ikki bosqichli:
 *   1. Telegram ID kiritiladi → bot 6 xonali kod yuboradi
 *   2. Kod kiritiladi → JWT olinadi
 *
 * Parol yo'q: Telegram hisobining o'zi identifikator bo'lib xizmat qiladi,
 * chunki ustozlar ham botga aynan shu orqali kiradi.
 */

const idSchema = z.object({
  telegram_id: z
    .string()
    .min(5, 'Telegram ID kamida 5 raqamdan iborat')
    .regex(/^\d+$/, 'Faqat raqam kiriting'),
})

const codeSchema = z.object({
  code: z
    .string()
    .length(6, 'Kod 6 xonali')
    .regex(/^\d+$/, 'Faqat raqam kiriting'),
})

type IdForm = z.infer<typeof idSchema>
type CodeForm = z.infer<typeof codeSchema>

export function LoginPage() {
  const { login } = useAuth()
  const [telegramId, setTelegramId] = useState<number | null>(null)
  const [secondsLeft, setSecondsLeft] = useState(0)

  // Kodni qayta so'rashgacha qolgan vaqt hisoblagichi.
  useEffect(() => {
    if (secondsLeft <= 0) return
    const timer = setInterval(() => setSecondsLeft((s) => Math.max(0, s - 1)), 1000)
    return () => clearInterval(timer)
  }, [secondsLeft])

  const idForm = useForm<IdForm>({
    resolver: zodResolver(idSchema),
    defaultValues: { telegram_id: '' },
  })
  const codeForm = useForm<CodeForm>({
    resolver: zodResolver(codeSchema),
    defaultValues: { code: '' },
  })

  const requestOtp = useMutation({
    mutationFn: async (values: IdForm) => {
      const { data } = await api.post<OtpRequestResult>(
        '/api/admin/auth/otp/request',
        { telegram_id: Number(values.telegram_id) },
      )
      return { data, telegramId: Number(values.telegram_id) }
    },
    onSuccess: ({ data, telegramId: id }) => {
      if (!data.ok && data.retry_after_seconds > 0) {
        setSecondsLeft(data.retry_after_seconds)
        toast.warning(data.message)
        return
      }
      setTelegramId(id)
      setSecondsLeft(60)
      toast.success(data.message)
    },
    onError: (error) => toast.error(errorMessage(error, 'Kod yuborilmadi')),
  })

  const verifyOtp = useMutation({
    mutationFn: async (values: CodeForm) => {
      const { data } = await api.post<TokenPair>('/api/admin/auth/otp/verify', {
        telegram_id: telegramId,
        code: values.code,
      })
      return data
    },
    onSuccess: (tokens) => {
      login(tokens)
      toast.success(`Xush kelibsiz, ${tokens.profile.full_name ?? 'admin'}!`)
    },
    onError: (error) => {
      toast.error(errorMessage(error, "Kod noto'g'ri"))
      codeForm.reset()
    },
  })

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="items-center text-center">
          <div className="mb-2 flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <ScanLine className="h-5 w-5" />
          </div>
          <CardTitle className="text-xl">OMR Admin Panel</CardTitle>
          <CardDescription>
            {telegramId === null
              ? 'Telegram ID raqamingizni kiriting — botga kirish kodi yuboriladi'
              : 'Botga kelgan 6 xonali kodni kiriting'}
          </CardDescription>
        </CardHeader>

        <CardContent>
          {telegramId === null ? (
            <form
              onSubmit={idForm.handleSubmit((values) => requestOtp.mutate(values))}
              className="space-y-4"
            >
              <div className="space-y-1.5">
                <Label htmlFor="telegram_id">Telegram ID</Label>
                <Input
                  id="telegram_id"
                  inputMode="numeric"
                  autoComplete="off"
                  placeholder="123456789"
                  {...idForm.register('telegram_id')}
                />
                {idForm.formState.errors.telegram_id && (
                  <p className="text-xs text-destructive">
                    {idForm.formState.errors.telegram_id.message}
                  </p>
                )}
                <p className="text-xs text-muted-foreground">
                  ID ni bilmasangiz — Telegram'da @userinfobot ga yozing.
                </p>
              </div>

              <Button
                type="submit"
                className="w-full"
                loading={requestOtp.isPending}
                disabled={secondsLeft > 0}
              >
                <Send className="h-4 w-4" />
                {secondsLeft > 0 ? `${secondsLeft} s kuting` : 'Kod yuborish'}
              </Button>
            </form>
          ) : (
            <form
              onSubmit={codeForm.handleSubmit((values) => verifyOtp.mutate(values))}
              className="space-y-4"
            >
              <div className="space-y-1.5">
                <Label htmlFor="code">Kirish kodi</Label>
                <Input
                  id="code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  autoFocus
                  maxLength={6}
                  placeholder="000000"
                  className="text-center text-2xl tracking-[0.5em]"
                  {...codeForm.register('code')}
                />
                {codeForm.formState.errors.code && (
                  <p className="text-xs text-destructive">
                    {codeForm.formState.errors.code.message}
                  </p>
                )}
              </div>

              <Button type="submit" className="w-full" loading={verifyOtp.isPending}>
                <ShieldCheck className="h-4 w-4" />
                Kirish
              </Button>

              <div className="flex items-center justify-between text-xs">
                <button
                  type="button"
                  className="flex items-center gap-1 text-muted-foreground hover:text-foreground"
                  onClick={() => {
                    setTelegramId(null)
                    codeForm.reset()
                  }}
                >
                  <ArrowLeft className="h-3 w-3" />
                  Orqaga
                </button>

                <button
                  type="button"
                  disabled={secondsLeft > 0 || requestOtp.isPending}
                  className="text-primary disabled:text-muted-foreground"
                  onClick={() =>
                    requestOtp.mutate({ telegram_id: String(telegramId) })
                  }
                >
                  {secondsLeft > 0
                    ? `Qayta yuborish (${secondsLeft}s)`
                    : 'Kodni qayta yuborish'}
                </button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

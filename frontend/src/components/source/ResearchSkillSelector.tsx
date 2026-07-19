'use client'

import { Lightbulb } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useTranslation } from '@/lib/hooks/use-translation'
import type {
  ResearchSkillMode,
  ResearchSkillSummary,
} from '@/lib/types/api'

const MAX_SELECTED_SKILLS = 3

const skillNameKeys = {
  'literature-doi-verification': 'literatureDoiVerification',
  'evidence-critical-appraisal': 'evidenceCriticalAppraisal',
  'competing-hypotheses': 'competingHypotheses',
  'doe-statistical-plan': 'doeStatisticalPlan',
  'chemical-identity-properties': 'chemicalIdentityProperties',
  'formulation-compatibility-matrix': 'formulationCompatibilityMatrix',
  'hthp-brine-validation': 'hthpBrineValidation',
  'scale-up-validation-gates': 'scaleUpValidationGates',
  'structured-research-report': 'structuredResearchReport',
  'oilwell-cement-additive-diagnosis': 'oilwellCementAdditiveDiagnosis',
} as const

type KnownResearchSkillId = keyof typeof skillNameKeys

interface ResearchSkillSelectorProps {
  skills: ResearchSkillSummary[]
  mode: ResearchSkillMode
  selectedIds: string[]
  disabled?: boolean
  onChange: (mode: ResearchSkillMode, selectedIds: string[]) => void
}

export function ResearchSkillSelector({
  skills,
  mode,
  selectedIds,
  disabled = false,
  onChange,
}: ResearchSkillSelectorProps) {
  const { t } = useTranslation()
  const knownSkills = skills.filter(
    (skill): skill is ResearchSkillSummary & { id: KnownResearchSkillId } =>
      skill.id in skillNameKeys
  )
  const triggerLabel = mode === 'auto'
    ? t.chat.researchSkillsAuto
    : mode === 'off'
      ? t.chat.researchSkillsOff
      : t.chat.researchSkillsSelected.replace('{count}', String(selectedIds.length))

  const toggleSkill = (skillId: string, checked: boolean) => {
    const nextIds = checked
      ? [...selectedIds, skillId].slice(0, MAX_SELECTED_SKILLS)
      : selectedIds.filter(id => id !== skillId)
    onChange(nextIds.length > 0 ? 'selected' : 'auto', nextIds)
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 gap-2 px-2 text-xs font-normal text-muted-foreground"
          disabled={disabled}
          aria-label={t.chat.researchSkills}
        >
          <Lightbulb className="h-3.5 w-3.5" />
          {triggerLabel}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-80">
        <DropdownMenuLabel>{t.chat.researchSkills}</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={mode === 'selected' ? '' : mode}
          onValueChange={(value) => onChange(value as ResearchSkillMode, [])}
        >
          <DropdownMenuRadioItem value="auto">
            {t.chat.researchSkillsAuto}
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="off">
            {t.chat.researchSkillsOff}
          </DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuLabel className="text-xs text-muted-foreground">
          {t.chat.researchSkillsChoose}
        </DropdownMenuLabel>
        {knownSkills.map(skill => {
          const checked = selectedIds.includes(skill.id)
          const limitReached = !checked && selectedIds.length >= MAX_SELECTED_SKILLS
          const nameKey = skillNameKeys[skill.id]
          return (
            <DropdownMenuCheckboxItem
              key={skill.id}
              checked={checked}
              disabled={limitReached}
              onCheckedChange={value => toggleSkill(skill.id, value === true)}
              onSelect={event => event.preventDefault()}
            >
              <span className="min-w-0 flex-1 truncate">
                {t.chat.researchSkillNames[nameKey]}
              </span>
              <span className="text-[10px] text-muted-foreground">
                v{skill.version}
              </span>
            </DropdownMenuCheckboxItem>
          )
        })}
        <DropdownMenuSeparator />
        <p className="px-2 py-1 text-[11px] leading-4 text-muted-foreground">
          {t.chat.researchSkillsLimit}
        </p>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

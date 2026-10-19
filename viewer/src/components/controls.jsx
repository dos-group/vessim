import { useId } from 'react'
import { navigate } from '../navigation.js'
import { columnGroups } from '../model.js'
import { displayUnit, unitOptions } from '../units.js'

// Single choices use native selects everywhere. Multiple choices use the same
// disclosure and checkbox list, preserving focus and scroll during updates.
export function Select({
  label,
  value,
  onChange,
  options,
  groups,
  id,
  className = '',
  ...props
}) {
  const generated = useId(),
    controlId = id || generated
  const items = (entries) =>
    entries.map(({ value, label, disabled }) => (
      <option key={value} value={value} disabled={disabled}>
        {label}
      </option>
    ))
  return (
    <label className={`select-control ${className}`} htmlFor={controlId}>
      <span>{label}</span>
      <select
        {...props}
        id={controlId}
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value)}
      >
        {groups
          ? groups.map((group) => (
              <optgroup key={group.label} label={group.label}>
                {items(group.options)}
              </optgroup>
            ))
          : items(options || [])}
      </select>
    </label>
  )
}
export function Checkbox({ label, checked, onChange, ...props }) {
  return (
    <label className="check-label">
      <input
        {...props}
        type="checkbox"
        checked={Boolean(checked)}
        onChange={(event) => onChange(event.target.checked)}
      />
      {label}
    </label>
  )
}
export function Picker({ label, children }) {
  return (
    <details className="column-picker">
      <summary className="button">{label}</summary>
      <div className="picker-options">{children}</div>
    </details>
  )
}
export function ChoiceGroup({ label, children }) {
  return (
    <fieldset className="column-group">
      <legend>{label}</legend>
      {children}
    </fieldset>
  )
}
export function UnitSelect({
  unit,
  magnitude,
  value = 'auto',
  onChange,
  label = 'Display unit',
  ...props
}) {
  if (unitOptions(unit).length < 2) return null
  return (
    <Select
      {...props}
      label="Unit"
      aria-label={label}
      className="unit-control"
      value={value}
      onChange={onChange}
      options={[
        { value: 'auto', label: `Auto (${displayUnit(unit, magnitude).unit})` },
        ...unitOptions(unit).map((o) => ({ value: o.unit, label: o.unit })),
      ]}
    />
  )
}
export function FieldSelect({
  label,
  id,
  columns,
  study,
  view,
  presentation,
  patch,
  value,
  onChange,
}) {
  const selected = columns.find((column) => column.id === value)
  return (
    <div className="field-control">
      <Select
        label={label}
        id={id}
        value={value}
        onChange={onChange}
        groups={columnGroups(columns, study.singleMicrogrid).map((group) => ({
          label: group.label,
          options: group.columns.map((c) => ({
            value: c.id,
            label: `${c.label}${presentation.unit(c) ? ` (${presentation.unit(c)})` : ''}`,
          })),
        }))}
      />
      {selected && (
        <UnitSelect
          label={`Display unit for ${label.toLowerCase()}`}
          unit={selected.unit}
          magnitude={view.magnitudes[value]}
          value={view.units[value]}
          onChange={(unit) =>
            patch((s) => ({ units: { ...s.units, [value]: unit } }))
          }
        />
      )}
    </div>
  )
}
export function Segmented({ label, value, options, onChange }) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          aria-pressed={value === option.value}
          disabled={option.disabled}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
export function Heading({ title, children, actions }) {
  return (
    <div className="heading">
      <div>
        <h1>{title}</h1>
        {children && <p>{children}</p>}
      </div>
      {actions}
    </div>
  )
}
export function Issues({ errors = [] }) {
  return (
    errors.length > 0 && (
      <details className="data-issues">
        <summary>
          {errors.length} data issue{errors.length === 1 ? '' : 's'}
        </summary>
        <ul>
          {errors.map((error, i) => (
            <li key={i}>{error}</li>
          ))}
        </ul>
      </details>
    )
  )
}

export function NavLink({ href, children, ...props }) {
  return (
    <a
      {...props}
      href={href}
      onClick={(event) => {
        if (
          event.button ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey
        )
          return
        event.preventDefault()
        navigate(href.slice(1))
      }}
    >
      {children}
    </a>
  )
}

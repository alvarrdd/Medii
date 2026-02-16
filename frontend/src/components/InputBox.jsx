import React, { useState } from 'react'

const InputBox = ({ onAnalyze, isLoading }) => {
  const [value, setValue] = useState('')

  const submit = (e) => {
    e.preventDefault()
    if (value.trim()) onAnalyze(value.trim())
  }

  return (
    <form onSubmit={submit} className="space-y-8">

      <label className="text-lg font-semibold text-primary">
        Մուտքագրեք Ձեր ախտանիշները
      </label>

      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Օրինակ՝ գլխացավ, տենդ, սրտխառնոց…"
        className="w-full h-40 p-6 border-2 border-[#c5b2f4] rounded-xl focus:ring-2 focus:ring-[#c5b2f4] resize-none"
        disabled={isLoading}
      />

      <button className="btn-primary w-full py-4 text-lg" disabled={!value || isLoading}>
        🔍 Վերլուծել
      </button>

    </form>
  )
}

export default InputBox

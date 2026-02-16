import React from 'react'

const EmergencyBanner = ({ emergencySymptoms, urgencyLevel }) => {
  if (!emergencySymptoms?.length) return null

  const isCritical = urgencyLevel === 'critical' || urgencyLevel === 'high'

  return (
    <div
      className="rounded-xl p-6 fade-in"
      style={{ backgroundColor: isCritical ? '#ffcccc' : '#fff4cc' }}
    >
      <h3 className="text-xl font-bold mb-3">
        {isCritical ? 'Շտապ բժշկական ուշադրություն' : 'Կարևոր բժշկական խորհուրդ'}
      </h3>

      <p className="font-semibold mb-2">Հայտնաբերված ախտանիշներ՝</p>
      <ul className="list-disc list-inside">
        {emergencySymptoms.map((s, i) => <li key={i}>{s}</li>)}
      </ul>

      <p className="font-bold mt-4">⚠️ Խնդրում ենք շտապ դիմել 103։</p>
    </div>
  )
}

export default EmergencyBanner


import React from 'react'

const ResultCard = ({ recommendation }) => {
  if (!recommendation) return null

  const urgencyLabel = {
    critical: 'ՇՏԱՊ վտանգ',
    high: 'Բարձր վտանգ',
    medium: 'Միջին վտանգ',
    low: 'Ցածր վտանգ'
  }

  // Get urgency color
  const getUrgencyColor = (level) => {
    switch(level) {
      case 'critical': return 'bg-red-100 text-red-800 border-red-300';
      case 'high': return 'bg-orange-100 text-orange-800 border-orange-300';
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      case 'low': return 'bg-green-100 text-green-800 border-green-300';
      default: return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  }

  // Calculate match percentage for each specialist
  const calculateMatchPercentage = (specialist) => {
    if (specialist.match_score) {
      return Math.round(specialist.match_score * 100);
    }

    // Fallback calculation based on diseases
    if (specialist.diseases && specialist.diseases.length > 0) {
      const total = specialist.diseases.reduce((sum, disease) =>
        sum + (disease.match_score || 0.7), 0
      );
      return Math.round((total / specialist.diseases.length) * 100);
    }

    // Default based on overall confidence
    return Math.round((recommendation.confidence || 0.7) * 100);
  }

  // Get top diseases for a specialist (up to 3)
  const getTopDiseases = (specialist) => {
    if (!specialist.diseases || specialist.diseases.length === 0) {
      return [];
    }

    // Sort by match score (highest first) and take top 3
    return [...specialist.diseases]
      .sort((a, b) => (b.match_score || 0) - (a.match_score || 0))
      .slice(0, 3);
  }

  return (
    <div className="space-y-6 fade-in">

      {/* Main Analysis Results */}
      <div className="medi-panel">
        <h2 className="text-2xl font-bold text-primary mb-4">
          Վերլուծության Արդյունքներ
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className={`p-4 rounded-xl border-2 ${getUrgencyColor(recommendation.urgency_level)}`}>
            <p className="text-sm font-semibold mb-1">Վտանգի մակարդակ</p>
            <p className="text-xl font-bold">{urgencyLabel[recommendation.urgency_level]}</p>
          </div>

          <div className="p-4 rounded-xl border-2 border-blue-200 bg-blue-50">
            <p className="text-sm font-semibold mb-1 text-blue-800">Վստահություն</p>
            <p className="text-xl font-bold text-blue-800">
              {(recommendation.confidence * 100).toFixed(0)}%
            </p>
          </div>

          <div className="p-4 rounded-xl border-2 border-purple-200 bg-purple-50">
            <p className="text-sm font-semibold mb-1 text-purple-800">Մասնագետներ</p>
            <p className="text-xl font-bold text-purple-800">
              {recommendation.specialists?.length || 0}
            </p>
          </div>
        </div>

        {recommendation.reasoning && (
          <div className="mt-4 p-4 bg-white/50 rounded-xl border border-gray-200">
            <h3 className="font-bold text-primary mb-2">Վերլուծություն</h3>
            <p className="text-gray-700">{recommendation.reasoning}</p>
          </div>
        )}
      </div>

      {/* Suggested Specialists with Match Percentage and Diseases */}
      {recommendation.specialists?.length > 0 && (
        <div className="medi-panel">
          <h3 className="text-xl font-bold text-primary mb-4">
            Առաջարկվող մասնագետներ
          </h3>

          <div className="space-y-4">
            {recommendation.specialists.map((spec, i) => {
              const matchPercentage = calculateMatchPercentage(spec);
              const topDiseases = getTopDiseases(spec);

              return (
                <div key={i} className="p-5 border border-[#c5b2f4] rounded-xl bg-white/70 hover:bg-white/90 transition-all duration-300">

                  {/* Specialist Header */}
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <p className="font-bold text-lg text-gray-800">{spec.name_hy}</p>
                      {spec.description_hy && (
                        <p className="text-sm text-gray-600 mt-1">{spec.description_hy}</p>
                      )}
                    </div>

                    {/* Match Percentage Badge */}
                    <div className="flex items-center">
                      <div className="text-right mr-3">
                        <span className="text-sm text-gray-600 block">Համապատասխանություն</span>
                        <span className="text-xl font-bold text-green-600">{matchPercentage}%</span>
                      </div>
                      <div className="w-20 bg-gray-200 rounded-full h-3">
                        <div
                          className="bg-gradient-to-r from-green-400 to-green-500 h-3 rounded-full"
                          style={{ width: `${matchPercentage}%` }}
                        ></div>
                      </div>
                    </div>
                  </div>

                  {/* Top Diseases */}
                  {topDiseases.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-gray-200">
                      <p className="text-sm font-semibold text-gray-700 mb-3 flex items-center">
                        <span className="mr-2">🩺</span> Հնարավոր հիվանդություններ
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {topDiseases.map((disease, idx) => (
                          <div
                            key={idx}
                            className="px-3 py-2 bg-gradient-to-r from-purple-50 to-pink-50 border border-purple-200 rounded-lg"
                          >
                            <div className="flex justify-between items-center">
                              <span className="text-sm font-medium text-gray-800">
                                {disease.name_hy}
                              </span>
                              {disease.match_score && (
                                <span className="ml-2 text-xs font-bold text-purple-600 bg-purple-100 px-2 py-0.5 rounded-full">
                                  {Math.round(disease.match_score * 100)}%
                                </span>
                              )}
                            </div>
                            {disease.description && (
                              <p className="text-xs text-gray-600 mt-1">{disease.description}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Specialist Details */}
                  {(spec.recommended_action || spec.urgency_note) && (
                    <div className="mt-4 pt-4 border-t border-gray-200">
                      <div className="flex flex-wrap gap-4">
                        {spec.recommended_action && (
                          <div className="flex items-center text-sm text-gray-700">
                            <span className="mr-2">💡</span>
                            <span>{spec.recommended_action}</span>
                          </div>
                        )}

                        {spec.urgency_note && (
                          <div className="flex items-center text-sm text-red-600">
                            <span className="mr-2">⚠️</span>
                            <span>{spec.urgency_note}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Summary Statistics */}
          <div className="mt-6 pt-6 border-t border-gray-300">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="text-center p-3 bg-gradient-to-r from-blue-50 to-blue-100/50 rounded-lg">
                <p className="text-xl font-bold text-blue-800">
                  {recommendation.specialists.length}
                </p>
                <p className="text-xs text-gray-600">Մասնագետներ</p>
              </div>

              <div className="text-center p-3 bg-gradient-to-r from-green-50 to-green-100/50 rounded-lg">
                <p className="text-xl font-bold text-green-800">
                  {Math.round(
                    recommendation.specialists.reduce((acc, spec) =>
                      acc + calculateMatchPercentage(spec), 0
                    ) / recommendation.specialists.length
                  )}%
                </p>
                <p className="text-xs text-gray-600">Միջին համապատասխանություն</p>
              </div>

              <div className="text-center p-3 bg-gradient-to-r from-purple-50 to-purple-100/50 rounded-lg">
                <p className="text-xl font-bold text-purple-800">
                  {recommendation.specialists.reduce((acc, spec) =>
                    acc + (spec.diseases?.length || 0), 0
                  )}
                </p>
                <p className="text-xs text-gray-600">Ընդհանուր հիվանդություններ</p>
              </div>

              <div className="text-center p-3 bg-gradient-to-r from-gray-50 to-gray-100/50 rounded-lg">
                <p className="text-xl font-bold" style={{ color: '#c5b2f4' }}>
                  {urgencyLabel[recommendation.urgency_level].split(' ')[0]}
                </p>
                <p className="text-xs text-gray-600">Գնահատական</p>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}

export default ResultCard

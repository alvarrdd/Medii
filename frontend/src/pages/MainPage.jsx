import React, { useState } from "react";
import axios from "axios";

import InputBox from "../components/InputBox";
import ResultCard from "../components/ResultCard";
import EmergencyBanner from "../components/EmergencyBanner";
import SOSButton from "../components/SOSButton";

import MediHeader from "../assets/medi-header.png";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const MainPage = () => {
  const [recommendation, setRecommendation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleAnalyze = async (symptoms) => {
    setIsLoading(true);
    setError(null);
    setRecommendation(null);

    try {
      const response = await axios.post(`${API_BASE_URL}/api/recommend`, {
        symptoms,
      });
      setRecommendation(response.data);
    } catch (err) {
      setError("Չհաջողվեց մշակել տվյալները։");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen relative z-0">

      {/* ========== HERO SECTION ========== */}
      <div
        className="relative w-full overflow-visible"
        style={{
          height: "580px",                           // FIXED: more space for Medi image
          backgroundImage: `url(${MediHeader})`,
          backgroundSize: "900px",
          backgroundRepeat: "no-repeat",
          backgroundPosition: "left 40px top 50px",
        }}
      >
        <div className="absolute inset-0 bg-white/5"></div>

        {/* INPUT PANEL */}
        <div
          className="
            w-full max-w-[480px]
            medi-panel fade-in
            absolute
            top-[50%]
            -translate-y-[50%]
            right-8 lg:right-16
            z-[50]
          "
        >
          {/* FIXED: More top spacing with mt-8 */}
          <div className="text-center space-y-3 mb-6 mt-8">
            <h1 className="text-3xl font-bold text-primary">
              Ախտանիշների Վերլուծություն
            </h1>
            <p className="text-gray-700">
              Մուտքագրեք Ձեր ախտանիշները ստորև և ստացեք AI գնահատում
            </p>
          </div>

          <InputBox onAnalyze={handleAnalyze} isLoading={isLoading} />

          {error && (
            <div className="mt-4 bg-red-100 border-l-4 border-red-500 p-4 rounded-xl">
              <p className="font-semibold text-red-700">{error}</p>
            </div>
          )}
        </div>
      </div>

      {/* ========== MAIN CONTENT BELOW HERO ========== */}
      <div className="relative z-10 mt-10">
        <div className="container mx-auto px-4 pb-20">

          {/* RESULTS */}
          {recommendation && (
            <div className="max-w-4xl mx-auto space-y-8 fade-in">
              <EmergencyBanner
                emergencySymptoms={recommendation.emergency_symptoms}
                urgencyLevel={recommendation.urgency_level}
              />
              <ResultCard recommendation={recommendation} />
            </div>
          )}

          {/* LOADING */}
          {isLoading && (
            <div className="max-w-4xl mx-auto text-center py-16 fade-in">
              <div className="animate-spin-slow mx-auto h-20 w-20 border-t-4 border-b-4 border-[#c5b2f4] rounded-full"></div>
              <p className="text-gray-600 mt-6 text-lg">Ախտանիշները վերլուծվում են…</p>
              <p className="text-sm text-gray-500 mt-2">Խնդրում ենք սպասել մի քանի վայրկյան</p>
            </div>
          )}

          {/* INFO SECTION */}
          {!recommendation && !isLoading && (
            <div className="max-w-4xl mx-auto mt-20 fade-in">
              <div className="medi-panel">
                <h2 className="text-2xl font-bold text-primary mb-6 text-center">
                  👨‍⚕️ Ինչպես է աշխատում Medi-ն
                </h2>

                <div className="grid md:grid-cols-3 gap-6 mb-8">

                  {/* STEP 1 */}
                  <div className="text-center p-6 bg-gradient-to-br from-blue-50/50 to-white rounded-xl border border-blue-100">
                    <div className="text-3xl mb-4">1</div>
                    <h3 className="font-bold text-lg text-gray-800 mb-2">
                      Մուտքագրեք Ձեր ախտանիշները
                    </h3>
                    <p className="text-gray-600">
                      Նշեք Ձեր հիմնական բողոքները՝ օրինակ «գլխացավ», «հազ», «սրտխառնոց»։
                    </p>
                  </div>

                  {/* STEP 2 */}
                  <div className="text-center p-6 bg-gradient-to-br from-purple-50/50 to-white rounded-xl border border-purple-100">
                    <div className="text-3xl mb-4">2</div>
                    <h3 className="font-bold text-lg text-gray-800 mb-2">
                      Medi-ն մշակում և համեմատում է ախտանիշները
                    </h3>
                    <p className="text-gray-600">
                      Համակարգը վերլուծում է տվյալները և գտնում հնարավոր հիվանդությունները՝
                      ըստ համապատասխանության տոկոսի։
                    </p>
                  </div>

                  {/* STEP 3 */}
                  <div className="text-center p-6 bg-gradient-to-br from-green-50/50 to-white rounded-xl border border-green-100">
                    <div className="text-3xl mb-4">3</div>
                    <h3 className="font-bold text-lg text-gray-800 mb-2">
                      Ստացեք մասնագետի առաջարկ
                    </h3>
                    <p className="text-gray-600">
                      Medi-ն առաջարկում է համապատասխան բժշկի տեսակը և ցույց է տալիս
                      յուրաքանչյուր հիվանդության հավանականությունը։
                    </p>
                  </div>

                </div>
              </div>
            </div>
          )}

        </div>
      </div>

      {/* FOOTER */}
      <footer
        className="py-10 mt-8 text-center"
        style={{
          background: "#fffaea",
          borderTop: "2px solid rgba(197,178,244,0.3)",
        }}
      >
        <p className="text-lg font-bold mb-2" style={{ color: "#c5b2f4" }}>
          Medi • Բժշկական AI օգնական
        </p>
        <p className="text-sm text-gray-600 max-w-2xl mx-auto">
          Medi-ն տրամադրում է նախնական առաջարկներ՝ հիմնված արհեստական բանականության վերլուծության վրա։
        </p>
      </footer>

      <SOSButton />
    </div>
  );
};

export default MainPage;


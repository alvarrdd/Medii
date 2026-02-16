import React, { useState } from 'react'

const SOSButton = () => {
  const [open, setOpen] = useState(false)

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-8 right-8 bg-red-500 text-white font-bold py-4 px-6 rounded-full shadow-xl text-lg"
      >
        🚨 Շտապ
      </button>

      {open && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white p-6 rounded-xl max-w-sm w-full">

            <h2 className="text-2xl font-bold text-red-600 text-center mb-3">
              ՇՏԱՊ ՕԳՆՈՒԹՅՈՒՆ
            </h2>

            <p className="text-gray-700 mb-6 text-center">
              Վտանգավոր վիճակում զանգահարեք 103։
            </p>

            <button
              onClick={() => (window.location.href = 'tel:103')}
              className="btn-primary w-full mb-3"
            >
              📞 Զանգել 103
            </button>

            <button
              onClick={() => setOpen(false)}
              className="w-full py-3 bg-gray-200 rounded-lg font-semibold"
            >
              Փակել
            </button>

          </div>
        </div>
      )}
    </>
  )
}

export default SOSButton


"use client";

import { useState, useEffect } from "react";
import { UploadCloud, FileText, ArrowRight, Loader2, CheckCircle2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import axios from "axios";
import { useRouter } from "next/navigation";

const RANDOM_FACTS = [
  "Honey never spoils. Archaeologists have found pots of honey in ancient Egyptian tombs that are over 3,000 years old and still perfectly edible.",
  "Octopuses have three hearts: two pump blood to the gills, and one pumps it to the rest of the body.",
  "Bananas are berries, but strawberries aren't. In botanical terms, berries are fleshy fruits produced from a single ovary.",
  "A day on Venus is longer than a year on Venus. It completes one rotation every 243 Earth days.",
  "Wombat poop is cube-shaped, which stops it from rolling away from their territory markings.",
  "The shortest commercial flight in the world takes just 57 seconds, between the Scottish islands of Westray and Papa Westray.",
  "A jiffy is an actual unit of time: 1/100th of a second.",
  "A group of flamingos is called a 'flamboyance'.",
  "There is a species of jellyfish that is biologically immortal.",
  "The Eiffel Tower can be 15 cm taller during the summer due to thermal expansion.",
  "Sloths can hold their breath longer than dolphins can, for up to 40 minutes.",
  "Peanuts are not nuts, they are legumes.",
  "A single cloud can weigh more than a million pounds.",
  "Cows have best friends and get stressed when separated.",
  "Pineapples take about two years to grow.",
  "Water can boil and freeze at the same time, known as the 'triple point'.",
  "A single strand of spider silk is thinner than a human hair but five times stronger than steel of the same width.",
  "Oxford University is older than the Aztec Empire.",
  "There are more trees on Earth than stars in the Milky Way galaxy.",
  "Vending machines kill more people each year than sharks do."
];

export default function Home() {
  const [files, setFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [fileStatuses, setFileStatuses] = useState<Record<string, "waiting" | "processing" | "done">>({});
  const [currentFact, setCurrentFact] = useState("");
  const router = useRouter();

  useEffect(() => {
    if (!isUploading) return;

    setCurrentFact(RANDOM_FACTS[Math.floor(Math.random() * RANDOM_FACTS.length)]);
    const interval = setInterval(() => {
      setCurrentFact(RANDOM_FACTS[Math.floor(Math.random() * RANDOM_FACTS.length)]);
    }, 10000);

    return () => clearInterval(interval);
  }, [isUploading]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      // Allow up to 5 files
      const selectedFiles = Array.from(e.target.files).slice(0, 5);
      setFiles(selectedFiles);
    }
  };

  const handleUpload = async () => {
    if (files.length < 2 || files.length > 5) return;
    setIsUploading(true);

    const initialStatuses: Record<string, "waiting" | "processing" | "done"> = {};
    files.forEach(f => initialStatuses[f.name] = "waiting");
    setFileStatuses(initialStatuses);

    try {
      // Wipe the database so each search is independent
      await axios.post("http://localhost:8000/reset");

      // Upload and process sequentially for better UI feedback and to prevent LLM rate limits
      for (const file of files) {
        setFileStatuses(prev => ({ ...prev, [file.name]: "processing" }));

        const formData = new FormData();
        formData.append("file", file);
        await axios.post("http://localhost:8000/upload", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });

        setFileStatuses(prev => ({ ...prev, [file.name]: "done" }));
      }

      // Let the dashboard handle the slow reconciliation pass asynchronously
      sessionStorage.setItem("needsReconciliation", "true");

      // Redirect to dashboard where the extracted facts will immediately be available
      router.push("/dashboard");
    } catch (error) {
      console.error("Upload failed", error);
      setIsUploading(false);
    }
  };

  const isUploadDisabled = isUploading || files.length < 2 || files.length > 5;

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-8 relative overflow-hidden">
      {/* Background decoration */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-600/20 rounded-full blur-[120px]" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-600/20 rounded-full blur-[120px]" />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="z-10 text-center max-w-3xl w-full"
      >
        <h1 className="text-6xl font-bold tracking-tight mb-4">
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-500">
            Fact Lens
          </span>
        </h1>
        <p className="text-xl text-slate-400 mb-12 font-light">
          Upload documents to instantly extract facts, discover cross-document corroborations, and identify contradictions.
        </p>

        <div className="glass-panel rounded-3xl p-8 shadow-2xl flex flex-col items-center justify-center border border-slate-700/50">

          <input
            type="file"
            id="file-upload"
            className="hidden"
            accept=".pdf"
            multiple
            onChange={handleFileChange}
          />

          {files.length === 0 ? (
            <>
              <div className="w-full flex justify-center mb-8">
                <div className="h-24 w-24 bg-blue-500/10 rounded-full flex items-center justify-center border border-blue-500/20">
                  <UploadCloud className="h-10 w-10 text-blue-400" />
                </div>
              </div>
              <label
                htmlFor="file-upload"
                className="cursor-pointer bg-slate-800 hover:bg-slate-700 text-white px-8 py-4 rounded-xl font-medium transition-all duration-300 flex items-center gap-3 border border-slate-600"
              >
                <FileText className="h-5 w-5" />
                Select PDF Documents (Min 2, Max 5)
              </label>
            </>
          ) : (
            <div className="flex flex-col items-center gap-6 w-full">
              <div className="flex justify-between w-full max-w-md items-end">
                <h3 className="text-slate-300 font-medium">Selected Documents</h3>
                {!isUploading && (
                  <label htmlFor="file-upload" className="text-blue-400 text-sm cursor-pointer hover:text-blue-300">
                    Change Files
                  </label>
                )}
              </div>

              <div className="flex flex-col gap-3 w-full max-w-md">
                {files.map((f, idx) => {
                  const status = fileStatuses[f.name] || "waiting";

                  return (
                    <div key={idx} className={`flex items-center justify-between px-5 py-4 rounded-xl border ${status === 'processing' ? 'bg-blue-900/20 border-blue-500/50' : status === 'done' ? 'bg-emerald-900/20 border-emerald-500/50' : 'bg-slate-800 border-slate-700'} transition-colors`}>
                      <div className="flex items-center gap-3 overflow-hidden">
                        <FileText className={`h-5 w-5 flex-shrink-0 ${status === 'processing' ? 'text-blue-400' : status === 'done' ? 'text-emerald-400' : 'text-purple-400'}`} />
                        <span className="truncate text-slate-200 font-medium">{f.name}</span>
                      </div>

                      {isUploading && (
                        <div className="flex-shrink-0 ml-4">
                          {status === 'processing' && (
                            <div className="flex items-center gap-2 text-blue-400 text-sm">
                              <Loader2 className="h-4 w-4 animate-spin" />
                              <span>Extracting...</span>
                            </div>
                          )}
                          {status === 'done' && (
                            <div className="flex items-center gap-2 text-emerald-400 text-sm">
                              <CheckCircle2 className="h-4 w-4" />
                              <span>Done</span>
                            </div>
                          )}
                          {status === 'waiting' && (
                            <span className="text-slate-500 text-sm">Waiting...</span>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {files.length < 2 && (
                <p className="text-red-400 text-sm bg-red-500/10 px-4 py-2 rounded-lg border border-red-500/20">
                  Please select at least 2 files to find cross-document relationships.
                </p>
              )}

              {files.length > 5 && (
                <p className="text-red-400 text-sm bg-red-500/10 px-4 py-2 rounded-lg border border-red-500/20">
                  Please select no more than 5 files.
                </p>
              )}

              <button
                onClick={handleUpload}
                disabled={isUploadDisabled}
                className={`w-full max-w-md px-8 py-4 rounded-xl font-medium transition-all duration-300 flex items-center justify-center gap-3 shadow-lg ${isUploadDisabled ? 'bg-slate-700 text-slate-400 cursor-not-allowed shadow-none' : 'bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white shadow-blue-500/25'}`}
              >
                {isUploading ? (
                  <>
                    <Loader2 className="h-5 w-5 animate-spin" />
                    Processing documents...
                  </>
                ) : (
                  <>
                    Extract Knowledge
                    <ArrowRight className="h-5 w-5" />
                  </>
                )}
              </button>
            </div>
          )}

          <AnimatePresence>
            {isUploading && currentFact && (
              <motion.div
                initial={{ opacity: 0, height: 0, marginTop: 0 }}
                animate={{ opacity: 1, height: "auto", marginTop: 32 }}
                exit={{ opacity: 0, height: 0, marginTop: 0 }}
                className="w-full max-w-md overflow-hidden"
              >
                <div className="bg-blue-900/20 border border-blue-500/30 rounded-xl p-6 text-left relative overflow-hidden">
                  <div className="absolute top-0 left-0 w-1 h-full bg-blue-500"></div>
                  <h4 className="text-blue-400 font-semibold mb-2 flex items-center gap-2 text-sm uppercase tracking-wider">
                    💡 Did you know?
                  </h4>
                  <motion.p
                    key={currentFact}
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5 }}
                    className="text-slate-300 text-sm leading-relaxed"
                  >
                    {currentFact}
                  </motion.p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {!isUploading && (
            <p className="text-slate-500 mt-6 text-sm">
              Powered by Gemini • Secure & Local
            </p>
          )}
        </div>
      </motion.div>
    </div>
  );
}

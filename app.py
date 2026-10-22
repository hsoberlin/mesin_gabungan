# -*- coding: utf-8 -*-
"""
MESIN GABUNGAN — Tahap 2 (mesin inti + alokasi kas + daftar order + state JSON)
Compounding Terminal (akun TEKNIKAL) + Harmonic Board Besar & Menengah (akun OBERLIN).

Tahap 1 (lulus uji kecocokan 23 Okt 2026):
  - Mode pasar IHSG 20 hari bursa (PANIK / NORMAL / EUFORIA), gerbang BEAR versi perbaikan.
  - Scan Harmonic bullish Besar + Menengah (detect_patterns asli) + Scan Compounding (analyze_stock asli).
Tahap 2:
  - Status sinyal harmonic SAH / TUA (aturan antrian GTC backtest).
  - State JSON dua akun (posisi, antrian, kas), impor portfolio.json Compounding Terminal.
  - Cek posisi (TP1 / stop / CL / K>80 / breakeven), cocokkan lot order TP-SL, status antrian.
  - Alokasi kas per mode, saran pindah kas TEKNIKAL -> OBERLIN saat PANIK, daftar order siap ketik.
  - Perbaikan tanggal IHSG yang tertinggal dari data saham, ringkasan jurnal siap salin.

Sesi pemakaian:
  - 15.00–16.15 WIB : sesi Compounding (candle berjalan, beli sebelum close, sama seperti app lama).
  - setelah 16.15   : sesi sore (data final) untuk harmonic, cek posisi, rekap.

Jalankan : streamlit run mesin_gabungan.py
Butuh    : streamlit>=1.50, yfinance, pandas, numpy
"""
import json
import math
import os
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except ImportError:
    yf = None
try:
    import plotly.graph_objects as go
except ImportError:
    go = None

WIB = timezone(timedelta(hours=7))


# =============================================================================
# 0. TEMA GELAP
# =============================================================================
def ensure_dark_config():
    path = os.path.join(os.getcwd(), ".streamlit", "config.toml")
    if os.path.exists(path):
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                '[theme]\nbase = "dark"\nprimaryColor = "#00ff9c"\n'
                'backgroundColor = "#06080b"\nsecondaryBackgroundColor = "#0d1218"\n'
                'textColor = "#d7e0ea"\nfont = "monospace"\n'
            )
    except Exception:
        pass


ensure_dark_config()

# =============================================================================
# 1. PARAMETER SISTEM GABUNGAN
# =============================================================================
PANIK_RET20 = -0.05          # IHSG 20 hari <= -5%  -> PANIK
EUFORIA_RET20 = 0.10         # IHSG 20 hari >  +10% -> EUFORIA (rem beli Compounding)

HB_SCALES = {"Besar": (5.0, 150), "Menengah": (3.0, 80)}   # mult ATR, umur maks C
HB_MAX_DIST = 15.0           # jarak maks harga ke PRZ (%)
HB_RR_MIN = 0.5              # R:R rencana minimal (sama dengan backtest)
HB_VAL_MIN = 1.0             # value terendah 20 hari minimal (miliar)
HB_UMUR_MAX = 220            # antrian GTC berlaku maks 220 hari kalender sejak sinyal aktif (backtest)
HB_SENTUH_MAX = 3            # PRZ disentuh pertama kali > 3 hari bursa lalu -> TUA, tanpa order
HB_PORSI = 0.10              # dana per antrian = 10% ekuitas (2 antrian per sinyal)
HB_MENENGAH_CAP = 0.20       # eksposur Menengah maks 20% ekuitas OBERLIN
CT_PORSI = 0.20              # Compounding 20% Total Modal Masuk per posisi
FEE_BELI = 0.0015
FEE_JUAL = 0.0025
TARIF_MATERAI = 10_000
HB_LEBAR_X = 2.0             # flag PRZ lebar: risiko dari antri atas > 2x potensi ke TP1
ARB_DEFAULT = 7.0            # ARB asimetris 7% (SK Kep-00157/BEI/10-2026, s.d. 31 Des 2026)

# Compounding (sama persis dengan compounding_terminal.py)
MIN_LIQUIDITY = 1_000_000_000
MIN_HEARTBEAT = 0.05
VOL_RATIO_MAX = 1.0
LL_PERIOD = 20
LOOKBACK_FASE = 120
HYSTERESIS_ENTER_BEAR = -0.20
HYSTERESIS_EXIT_BEAR = -0.10
RECOVERY_DARI_TROUGH = 1.20
AMBANG_CONF_BEAR = 80
AMBANG_CONF_NORMAL = 0

RED_FLAG = set("AGAR DOOH BIKE AYAM MGLV VISI JARR PGUN TEBE MDIA SINI FORU PIPA JGLE "
               "VKTR SGER IRSX BREN TPIA MMIX PEGE MEJA PACK".split())

# =============================================================================
# 2. UNIVERSE (disalin dari masing-masing aplikasi lama)
# =============================================================================
HB_UNIVERSE = """
AADI AALI ABBA ABDA ABMM ACES ACRO ACST ADCP ADES ADHI ADMF ADMG ADMR ADRO AEGS AGAR AGII AGRO
AGRS AHAP AIMS AISA AKKU AKPI AKRA AKSI ALDO ALII ALKA ALMI ALTO AMAG AMAN AMAR AMFG AMIN AMMN
AMMS AMOR AMRT ANDI ANJT ANTM APEX APIC APII APLI APLN ARCI AREA ARGO ARII ARKA ARKO ARMY ARNA
ARTA ARTI ARTO ASBI ASDM ASGR ASHA ASII ASJT ASLC ASLI ASMI ASPI ASRI ASRM ASSA ATAP ATIC ATLA
AUTO AVIA AWAN AXIO AYAM AYLS BABP BABY BACA BAIK BAJA BALI BANK BAPA BAPI BATA BATR BAUT BAYU
BBCA BBHI BBKP BBLD BBMD BBNI BBRI BBRM BBSI BBSS BBTN BBYB BCAP BCIC BCIP BDKR BDMN BEBS BEEF
BEER BEKS BELI BELL BESS BEST BFIN BGTG BHAT BHIT BIKA BIKE BIMA BINA BINO BIPI BIPP BIRD BISI
BJBR BJTM BKDP BKSL BKSW BLES BLTA BLTZ BLUE BMAS BMBL BMHS BMRI BMSR BMTR BNBA BNBR BNGA BNII
BNLI BOAT BOBA BOGA BOLA BOLT BOSS BPFI BPII BPTR BRAM BREN BRIS BRMS BRNA BRPT BRRC BSBK BSDE
BSIM BSML BSSR BSWD BTEK BTEL BTON BTPN BTPS BUAH BUDI BUKA BUKK BULL BUMI BUVA BVIC BWPT BYAN
CAKK CAMP CANI CARE CARS CASA CASH CASS CBDK CBMF CBPE CBRE CBUT CCSI CEKA CENT CFIN CGAS CHEM
CHIP CINT CITA CITY CLAY CLEO CLPI CMNP CMNT CMPP CMRY CNKO CNMA CNTX COAL COCO COWL CPIN CPRI
CPRO CRAB CRSN CSAP CSIS CSMI CSRA CTBN CTRA CTTH CUAN CYBR DAAZ DADA DART DATA DAYA DCII DEAL
DEFI DEPO DEWA DEWI DFAM DGIK DGNS DGWG DIGI DILD DIVA DKFT DLTA DMAS DMMX DMND DNAR DNET DOID
DOOH DOSS DPNS DPUM DRMA DSFI DSNG DSSA DUCK DUTI DVLA DWGL DYAN EAST ECII EDGE EKAD ELIT ELPI
ELSA ELTY EMDE EMTK ENAK ENRG ENVY ENZO EPAC EPMT ERAA ERAL ERTX ESIP ESSA ESTA ESTI ETWA EURO
EXCL FAPA FAST FASW FILM FIMP FIRE FISH FITT FLMC FMII FOLK FOOD FORU FORZ FPNI FREN FUJI FUTR
FWCT GAMA GDST GDYR GEMA GEMS GGRM GGRP GHON GIAA GJTL GLOB GLVA GMFI GMTD GOLD GOLF GOLL GOOD
GOTO GPRA GPSO GRIA GRPH GRPM GSMF GTBO GTRA GTSI GULA GUNA GWSA GZCO HADE HAIS HAJJ HALO HATM
HBAT HDFA HDIT HDTX HEAL HELI HERO HEXA HGII HILL HITS HKMU HMSP HOKI HOME HOMI HOPE HOTL HRME
HRTA HRUM HUMI HYGN IATA IBFN IBOS IBST ICBP ICON IDEA IDPR IFII IFSH IGAR IIKP IKAI IKAN IKBI
IKPM IMAS IMJS IMPC INAF INAI INCF INCI INCO INDF INDO INDR INDS INDX INDY INET INKP INOV INPC
INPP INPS INRU INTA INTD INTP IOTF IPAC IPCC IPCM IPOL IPPE IPTV IRRA IRSX ISAP ISAT ISEA ISSP
ITIC ITMA ITMG JARR JAST JATI JAWA JAYA JECC JGLE JIHD JKON JKSW JMAS JPFA JRPT JSKY JSMR JSPT
JTPE KAEF KARW KAYU KBAG KBLI KBLM KBLV KBRI KDSI KDTN KEEN KEJU KETR KIAS KICI KIJA KING KINO
KIOS KJEN KKES KKGI KLAS KLBF KLIN KMDS KMTR KOBX KOCI KOIN KOKA KONI KOPI KOTA KPAL KPAS KPIG
KRAH KRAS KREN KRYA KSIX KUAS LABA LABS LAJU LAND LAPD LCGP LCKM LEAD LFLO LIFE LINK LION LIVE
LMAS LMAX LMPI LMSH LOPI LPCK LPGI LPIN LPKR LPLI LPPF LPPS LRNA LSIP LTLS LUCK LUCY MABA MAGP
MAHA MAIN MAMI MANG MAPA MAPB MAPI MARI MARK MASA MASB MAXI MAYA MBAP MBMA MBSS MBTO MCAS MCOL
MCOR MDIA MDIY MDKA MDKI MDLN MDRN MEDC MEDS MEGA MEJA MENN MERK META MFIN MFMI MGLV MGNA MGRO
MHKI MICE MIDI MIKA MINA MIRA MITI MKAP MKNT MKPI MKTR MLBI MLIA MLPL MLPT MMIX MMLP MNCN MOLI
MORA MPIX MPMX MPOW MPPA MPRO MPXL MRAT MREI MSIE MSIN MSJA MSKY MSTI MTDL MTEL MTFN MTLA MTMH
MTPS MTRA MTSM MTWI MUTU MYOH MYOR MYRX MYTX NAIK NANO NASA NASI NATO NAYZ NCKL NELY NEST NETV
NFCX NICE NICK NICL NIKL NINE NIPS NIRO NISP NOBU NPGF NRCA NSSS NTBK NUSA NZIA OASA OBAT OBMD
OCAP OILS OKAS OLIV OMED OMRE OPMS PACK PADA PADI PALM PAMG PANI PANR PANS PART PBID PBRX PBSA
PCAR PDES PDPP PEGE PEHA PEVE PGAS PGEO PGJO PGLI PGUN PICO PIPA PJAA PKPK PLAN PLAS PLIN PMJS
PMMP PNBN PNBS PNGO PNIN PNLF PNSE POLA POLI POLL POLU POLY POOL PORT POSA POWR PPGL PPRE PPRI
PPRO PRAS PRAY PRDA PRIM PSAB PSDN PSGO PSKT PSSI PTBA PTDU PTIS PTMP PTMR PTPP PTPS PTPW PTRO
PTSN PTSP PUDP PURA PURE PURI PWON PYFA PZZA RAAM RAFI RAJA RALS RANC RATU RBMS RCCC RDTX REAL
RELF RELI RGAS RICY RIGS RIMO RISE RMKE RMKO ROCK RODA RONY ROTI RSCH RSGK RUIS RUNS SAFE SAGE
SAME SAMF SAPX SATU SBAT SBMA SCCO SCMA SCNP SCPI SDMU SDPC SDRA SEMA SFAN SGER SGRO SHID SHIP
SICO SIDO SILO SIMA SIMP SINI SIPD SKBM SKLT SKRN SKYB SLIS SMAR SMBR SMCB SMDM SMDR SMGA SMGR
SMIL SMKL SMKM SMLE SMMA SMMT SMRA SMRU SMSM SNLK SOCI SOFA SOHO SOLA SONA SOSS SOTS SOUL SPMA
SPRE SPTO SQMI SRAJ SRIL SRSN SRTG SSIA SSMS SSTM STAA STAR STRK STTP SUGI SULI SUNI SUPR SURE
SURI SWAT SWID TALF TAMA TAMU TAPG TARA TAXI TAYS TBIG TBLA TBMS TCID TCPI TDPM TEBE TECH TELE
TFAS TFCO TGKA TGRA TGUK TIFA TINS TIRA TIRT TKIM TLDN TLKM TMAS TMPO TNCA TOBA TOOL TOPS TOSK
TOTL TOTO TOWR TOYS TPIA TPMA TRAM TRGU TRIL TRIM TRIN TRIO TRIS TRJA TRON TRST TRUE TRUK TRUS
TSPC TUGU TYRE UANG UCID UDNG UFOE ULTJ UNIC UNIQ UNIT UNSP UNTD UNTR UNVR URBN UVCR VAST VERN
VICI VICO VINS VISI VIVA VKTR VOKS VRNA VTNY WAPO WEGE WEHA WGSH WICO WIDI WIFI WIIM WIKA WINE
WINR WINS WIRG WMPP WMUU WOMF WOOD WOWS WSBP WSKT WTON YELO YOII YPAS YULE ZATA ZBRA ZINC ZONE
ZYRX
"""

CT_UNIVERSE = """AADI, AALI, ABDA, ABMM, ACES, ACRO, ACST, ADCP, ADES, ADHI, ADMF, ADMG,
ADMR, ADRO, AGAR, AGII, AGRO, AGRS, AHAP, AISA, AKKU, AKPI, AKRA, AKSI,
ALDO, ALII, ALKA, ALMI, AMAG, AMAN, AMAR, AMFG, AMIN, AMMN, AMMS, AMOR,
AMRT, ANDI, ANJT, ANTM, APEX, APIC, APII, APLI, APLN, ARCI, AREA, ARGO,
ARII, ARKO, ARNA, ARTA, ARTO, ASDM, ASGR, ASHA, ASII, ASJT, ASLC, ASLI,
ASPI, ASPR, ASRI, ASRM, ASSA, ATAP, ATIC, ATLA, AUTO, AVIA, AWAN, AXIO,
AYAM, BABP, BABY, BACA, BACH, BAIK, BAJA, BALI, BANK, BATR, BAUT, BAYU,
BBCA, BBHI, BBKP, BBLD, BBMD, BBNI, BBRI, BBRM, BBSI, BBSS, BBTN, BBYB,
BCAP, BCIC, BDKR, BDMN, BEBS, BEEF, BEER, BEKS, BELI, BELL, BESS, BEST,
BFIN, BGTG, BHAT, BHIT, BIKE, BINA, BINO, BIPI, BIPP, BIRD, BISI, BJBR,
BJTM, BKDP, BKSL, BKSW, BLES, BLOG, BLTA, BLTZ, BLUE, BMAS, BMHS, BMRI,
BMSR, BMTR, BNBA, BNBR, BNGA, BNII, BNLI, BOAT, BOBA, BOGA, BOLA, BOLT,
BPFI, BPII, BPTR, BRAM, BREN, BRIS, BRMS, BRNA, BRPT, BSBK, BSDE, BSIM,
BSML, BSSR, BSWD, BTEK, BTON, BTPN, BTPS, BUAH, BUDI, BUKA, BUKK, BULL,
BUMI, BUVA, BVIC, BWPT, BYAN, CAKK, CAMP, CARE, CARS, CASA, CASH, CASS,
CBDK, CBPE, CBRE, CBUT, CCSI, CDIA, CEKA, CENT, CFIN, CGAS, CHEK, CHIP,
CINT, CITA, CITY, CLAY, CLEO, CLPI, CMNP, CMNT, CMPP, CMRY, CNKO, CNMA,
COAL, COCO, COIN, CPIN, CPRO, CRAB, CRSN, CSAP, CSIS, CSRA, CTBN, CTRA,
CUAN, CYBR, DAAZ, DADA, DART, DATA, DAYA, DCII, DEPO, DEWA, DEWI, DGIK,
DGNS, DGWG, DILD, DIVA, DKFT, DKHH, DLTA, DMAS, DMMX, DMND, DNAR, DNET,
DOID, DOOH, DOSS, DPUM, DRMA, DSFI, DSNG, DSSA, DUTI, DVLA, DWGL, DYAN,
EAST, ECII, EDGE, EKAD, ELIT, ELPI, ELSA, ELTY, EMAS, EMDE, EMMI, EMTK,
ENAK, ENRG, EPAC, EPMT, ERAA, ERAL, ERTX, ESSA, ESTA, ESTI, EURO, EXCL,
FAPA, FAST, FASW, FILM, FIRE, FISH, FITT, FMII, FOLK, FORE, FORU, FPNI,
FUJI, FUTR, FWCT, GDST, GDYR, GEMS, GGRM, GGRP, GHON, GIAA, GJTL, GLOB,
GLVA, GMFI, GMTD, GOLD, GOLF, GOOD, GOTO, GPRA, GPSO, GRIA, GRPM, GSMF,
GTBO, GTRA, GTSI, GULA, GUNA, GWSA, GZCO, HAIS, HAJJ, HALO, HATM, HBAT,
HDFA, HEAL, HELI, HERO, HEXA, HILL, HITS, HMSP, HOKI, HOMI, HOPE, HRME,
HRTA, HRUM, HUMI, HYGN, IATA, IBOS, IBST, ICBP, IDPR, IFII, IFSH, IGAR,
IKAI, IKBI, IKPM, IMAS, IMJS, IMPC, INAF, INCO, INDF, INDO, INDR, INDS,
INDY, INET, INKP, INOV, INPC, INPP, INPS, INRU, INTA, INTD, INTP, IOTF,
IPAC, IPCC, IPCM, IPOL, IPTV, IRRA, IRSX, ISAT, ISSP, ITIC, ITMA, ITMG,
JARR, JATI, JAWA, JECC, JECX, JELI, JGLE, JIHD, JKON, JMAS, JPFA, JRPT,
JSMR, JSPT, JTPE, KAEF, KAQI, KBAG, KBLI, KBLM, KBLV, KDSI, KDTN, KEEN,
KEJU, KETR, KIAS, KIJA, KING, KINO, KKGI, KLAS, KLBF, KMDS, KMTR, KOBX,
KOCI, KOKA, KONI, KOTA, KPIG, KRAS, KREN, KSIX, LABS, LAND, LAPD, LEAD,
LFLO, LIFE, LINK, LION, LIVE, LMPI, LPCK, LPGI, LPIN, LPKR, LPLI, LPPF,
LPPS, LSIP, LTLS, LUCY, MAHA, MAIN, MAPA, MAPB, MAPI, MARK, MASB, MAXI,
MAYA, MBAP, MBMA, MBSS, MCAS, MCOL, MCOR, MDIA, MDIY, MDKA, MDKI, MDLA,
MDLN, MDRN, MEDC, MEGA, MEJA, MERK, MFMI, MGLV, MGNA, MGRO, MHKI, MICE,
MIDI, MIKA, MINA, MINE, MKAP, MKPI, MKTR, MLBI, MLIA, MLPL, MLPT, MMIX,
MMLP, MNCN, MOLI, MORA, MPIX, MPMX, MPPA, MPRO, MPXL, MRAT, MREI, MSIN,
MSJA, MSKY, MSTI, MTDL, MTEL, MTFN, MTLA, MTMH, MTPS, MTWI, MUTU, MYOH,
MYOR, MYTX, NAIK, NASA, NATO, NAYZ, NCKL, NELY, NEST, NETV, NFCX, NICE,
NICK, NICL, NIKL, NINE, NIRO, NISP, NOBU, NPGF, NRCA, NSSS, NTBK, NZIA,
OASA, OBAT, OBMD, OKAS, OMED, OMRE, PACK, PADA, PADI, PALM, PAMG, PANI,
PANR, PANS, PART, PBID, PBRX, PBSA, PDES, PDPP, PEGE, PEHA, PEVE, PGAS,
PGEO, PGJO, PGUN, PIPA, PJAA, PJHB, PKPK, PLIN, PMJS, PMUI, PNBN, PNBS,
PNGO, PNIN, PNLF, PNSE, POLA, POLI, POLU, PORT, POWR, PPGL, PPRE, PPRO,
PRAY, PRDA, PRDL, PRIM, PSAB, PSAT, PSDN, PSGO, PSKT, PSSI, PTBA, PTMP,
PTMR, PTPP, PTPS, PTPW, PTRO, PTSN, PTSP, PUDP, PURA, PWON, PYFA, PZZA,
RAAM, RAJA, RALS, RANC, RANS, RATU, RBMS, RDTX, REAL, RELF, RELI, RGAS,
RIGS, RISE, RLCO, RMKE, RMKO, ROCK, RODA, RONY, ROTI, RSCH, SAFE, SAGE,
SAME, SAMF, SAPX, SATU, SCCO, SCMA, SCNP, SDMU, SDPC, SDRA, SFAN, SGER,
SGRO, SHID, SHIP, SIDO, SILO, SIMP, SINI, SIPD, SKBM, SKLT, SKRN, SLIS,
SMAR, SMBR, SMCB, SMDM, SMDR, SMGA, SMGR, SMIL, SMKL, SMLE, SMMA, SMMT,
SMRA, SMSM, SOCI, SOFA, SOHO, SOLA, SONA, SOSS, SOTS, SPMA, SPTO, SQMI,
SRAJ, SRSN, SRTG, SSIA, SSMS, SSTM, STAA, STAR, STRK, STTP, SULI, SUNI,
SUPA, SUPR, SURE, SURI, SWID, TALF, TAMA, TAMU, TAPG, TARA, TBIG, TBLA,
TCID, TCPI, TEBE, TFAS, TFCO, TGKA, TGUK, TIFA, TINS, TIRA, TIRT, TKIM,
TLDN, TLKM, TMAS, TMPO, TOBA, TOSK, TOTL, TOTO, TOWR, TPIA, TPMA, TRGU,
TRIM, TRIN, TRIS, TRJA, TRON, TRST, TRUE, TRUK, TRUS, TSPC, TUGU, TYRE,
UANG, UCID, UDNG, UFOE, ULTJ, UNIC, UNIQ, UNSP, UNTD, UNTR, UNVR, URBN,
UVCR, VAST, VERN, VICI, VICO, VINS, VISI, VIVA, VKTR, VOKS, VRNA, VTNY,
WAPO, WBSA, WEGE, WEHA, WGSH, WICO, WIFI, WIIM, WIKA, WINE, WINS, WIRG,
WMPP, WMUU, WOMF, WOOD, WSBP, WTON, XSPI, YELO, YOII, YPAS, YULE, YUPI,
ZATA, ZINC, ZONE, ZYRX"""


def parse_codes(text):
    raw = text.replace(",", " ").replace(";", " ").replace("\n", " ").split()
    out = []
    for t in raw:
        t = t.strip().upper().replace(".JK", "")
        if t.isalnum() and 2 <= len(t) <= 6 and t not in out:
            out.append(t)
    return out


HB_TICKERS = parse_codes(HB_UNIVERSE)
CT_TICKERS = sorted(set(parse_codes(CT_UNIVERSE)))
ALL_TICKERS = tuple(sorted(set(HB_TICKERS) | set(CT_TICKERS)))

# =============================================================================
# 3. INTI HARMONIC BOARD (disalin apa adanya dari harmonic_board_app.py)
# =============================================================================
PATTERNS = {
    "Alt Bat":   dict(b=(0.300, 0.382), d=1.130, sl=1.272, extra=[0.886]),
    "Bat":       dict(b=(0.382, 0.500), d=0.886, sl=1.130, extra=[]),
    "Gartley":   dict(b=(0.588, 0.648), d=0.786, sl=1.000, extra=[]),
    "Butterfly": dict(b=(0.756, 0.816), d=1.272, sl=1.414, extra=[]),
}
C_RANGE = (0.382, 0.886)
BC_EXT = (1.618, 2.0, 2.24, 2.618)
TP_RATIOS = (0.382, 0.618)
C_LOOKBACK = 8
X_LOOKBACK = 4


def atr_wilder(h, l, c, n=14):
    pc = np.roll(c, 1)
    pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean().values


def zigzag_atr(h, l, atr, mult):
    n = len(h)
    valid = np.where(~np.isnan(atr))[0]
    if len(valid) == 0:
        return [], None
    s = valid[0]
    piv = []
    trend = 0
    hi, hi_i, lo, lo_i = h[s], s, l[s], s
    ext, ext_i = None, None
    for i in range(s + 1, n):
        th = mult * atr[i]
        if trend == 0:
            if h[i] > hi:
                hi, hi_i = h[i], i
            if l[i] < lo:
                lo, lo_i = l[i], i
            if lo_i < i and h[i] - lo >= th:
                piv.append((lo_i, lo, "L"))
                seg = h[lo_i + 1:i + 1]
                k = int(np.argmax(seg))
                ext, ext_i, trend = seg[k], lo_i + 1 + k, 1
            elif hi_i < i and hi - l[i] >= th:
                piv.append((hi_i, hi, "H"))
                seg = l[hi_i + 1:i + 1]
                k = int(np.argmin(seg))
                ext, ext_i, trend = seg[k], hi_i + 1 + k, -1
        elif trend == 1:
            if h[i] > ext:
                ext, ext_i = h[i], i
            elif ext - l[i] >= th:
                piv.append((ext_i, ext, "H"))
                seg = l[ext_i + 1:i + 1]
                k = int(np.argmin(seg))
                ext, ext_i, trend = seg[k], ext_i + 1 + k, -1
        else:
            if l[i] < ext:
                ext, ext_i = l[i], i
            elif h[i] - ext >= th:
                piv.append((ext_i, ext, "L"))
                seg = h[ext_i + 1:i + 1]
                k = int(np.argmax(seg))
                ext, ext_i, trend = seg[k], ext_i + 1 + k, 1
    tent = None
    if trend != 0:
        tent = (ext_i, ext, "H" if trend == 1 else "L")
    return piv, tent


def zigzag_locks(h, l, atr, mult):
    """Sama dengan zigzag_atr, ditambah indeks hari saat tiap swing TERKUNCI (dari backtest)."""
    n = len(h)
    valid = np.where(~np.isnan(atr))[0]
    if len(valid) == 0:
        return [], []
    s = valid[0]
    piv, lk = [], []
    trend = 0
    hi, hi_i, lo, lo_i = h[s], s, l[s], s
    ext = ext_i = None
    for i in range(s + 1, n):
        th = mult * atr[i]
        if trend == 0:
            if h[i] > hi:
                hi, hi_i = h[i], i
            if l[i] < lo:
                lo, lo_i = l[i], i
            if lo_i < i and h[i] - lo >= th:
                piv.append((lo_i, lo, "L")); lk.append(i)
                seg = h[lo_i + 1:i + 1]; k = int(np.argmax(seg))
                ext, ext_i, trend = seg[k], lo_i + 1 + k, 1
            elif hi_i < i and hi - l[i] >= th:
                piv.append((hi_i, hi, "H")); lk.append(i)
                seg = l[hi_i + 1:i + 1]; k = int(np.argmin(seg))
                ext, ext_i, trend = seg[k], hi_i + 1 + k, -1
        elif trend == 1:
            if h[i] > ext:
                ext, ext_i = h[i], i
            elif ext - l[i] >= th:
                piv.append((ext_i, ext, "H")); lk.append(i)
                seg = l[ext_i + 1:i + 1]; k = int(np.argmin(seg))
                ext, ext_i, trend = seg[k], ext_i + 1 + k, -1
        else:
            if l[i] < ext:
                ext, ext_i = l[i], i
            elif h[i] - ext >= th:
                piv.append((ext_i, ext, "L")); lk.append(i)
                seg = h[ext_i + 1:i + 1]; k = int(np.argmax(seg))
                ext, ext_i, trend = seg[k], ext_i + 1 + k, 1
    return piv, lk


def classify_b(br):
    for name, p in PATTERNS.items():
        lo, hi = p["b"]
        if name == "Bat":
            if lo < br <= hi:
                return name
        elif lo <= br <= hi:
            return name
    return None


def build_zone(a, xa, c, bc_len, r):
    xa_lvl = a - r * xa
    best_e, best_lvl = None, None
    for e in BC_EXT:
        lvl = c - e * bc_len
        if best_lvl is None or abs(lvl - xa_lvl) < abs(best_lvl - xa_lvl):
            best_e, best_lvl = e, lvl
    return dict(r=r, xa_lvl=xa_lvl, bc_e=best_e, bc_lvl=best_lvl,
                top=max(xa_lvl, best_lvl), bot=min(xa_lvl, best_lvl))


def idx_tick(price):
    """Fraksi harga BEI."""
    p = abs(price)
    if p < 200:
        return 1
    if p < 500:
        return 2
    if p < 2000:
        return 5
    if p < 5000:
        return 10
    return 25


def round_tick(price, mode):
    t = idx_tick(price)
    q = price / t
    v = (np.floor(q + 1e-9) if mode == "down" else np.ceil(q - 1e-9)) * t
    t2 = idx_tick(v)
    if t2 != t:
        q = price / t2
        v = (np.floor(q + 1e-9) if mode == "down" else np.ceil(q - 1e-9)) * t2
    return float(v)


def pick_x(piv, ai, s):
    a_or = s * piv[ai][1]
    best = None
    for k in range(X_LOOKBACK):
        xi = ai - 1 - 2 * k
        if xi < 0:
            break
        x_or = s * piv[xi][1]
        mid = [s * q[1] for q in piv[xi + 1:ai]]
        if mid and (min(mid) < x_or or max(mid) > a_or):
            break
        if best is None or x_or < s * best[1]:
            best = piv[xi]
    return best


def detect_patterns(df, atr_len=14, mult=1.5, max_age=40, stats=None,
                    stop_basis="Low intraday", buf_atr=0.0):
    if stats is None:
        stats = {}
    for k in ("jendela", "lolos_c", "lolos_b", "lolos_umur", "aktif"):
        stats.setdefault(k, 0)
    h = df["High"].values.astype(float)
    l = df["Low"].values.astype(float)
    c = df["Close"].values.astype(float)
    n = len(df)
    atr = atr_wilder(h, l, c, atr_len)
    piv, tent = zigzag_atr(h, l, atr, mult)
    out = []
    for ci in range(len(piv) - 1, max(2, len(piv) - 1 - C_LOOKBACK), -1):
        if ci < 3:
            continue
        A, B, C = piv[ci - 2:ci + 1]
        s = 1 if A[2] == "H" else -1
        X = pick_x(piv, ci - 2, s)
        if X is None:
            continue
        x, a, b, cc = s * X[1], s * A[1], s * B[1], s * C[1]
        xa, ab = a - x, a - b
        if xa <= 0 or ab <= 0:
            continue
        lookback = ci < len(piv) - 2
        if lookback:
            opp = (h if s == 1 else -l)[C[0] + 1:]
            if len(opp) == 0 or float(opp.max()) > cc:
                continue
        stats["jendela"] += 1
        br = ab / xa
        cr = (cc - b) / ab
        if not (C_RANGE[0] <= cr <= C_RANGE[1]):
            continue
        stats["lolos_c"] += 1
        name = classify_b(br)
        if name is None:
            continue
        stats["lolos_b"] += 1
        age = (n - 1) - C[0]
        if age > max_age:
            continue
        stats["lolos_umur"] += 1

        p = PATTERNS[name]
        bc_len = cc - b
        zones = [build_zone(a, xa, cc, bc_len, p["d"])] + \
                [build_zone(a, xa, cc, bc_len, r) for r in p["extra"]]
        entry = a - p["d"] * xa
        sl = a - p["sl"] * xa
        tp1 = entry + TP_RATIOS[0] * (a - entry)
        tp2 = entry + TP_RATIOS[1] * (a - entry)
        if s == 1 and (sl <= 0 or min(z["bot"] for z in zones) <= 0):
            continue
        low_or = l if s == 1 else -h
        path = low_or[C[0] + 1:]
        if len(path) == 0:
            continue
        pmin = float(path.min())
        atr_c = float(atr[C[0]]) if not np.isnan(atr[C[0]]) else float(np.nanmean(atr))
        sl_eff = sl - buf_atr * atr_c
        chk = (s * c[C[0] + 1:]) if stop_basis == "Close harian" else path
        chk_min = float(chk.min())
        hit = np.where(path <= entry)[0]
        touch_idx = int(C[0] + 1 + hit[0]) if len(hit) else None
        reach_top = max(z["top"] for z in zones)
        d_locked = (ci == len(piv) - 2)

        hi_or = (h if s == 1 else -l)[C[0] + 1:]
        t_prz = np.where(path <= reach_top)[0]
        t_sl = np.where(chk < sl_eff)[0]
        t_sl = int(t_sl[0]) if len(t_sl) else None
        tp_hit, t_tp = None, None
        if len(t_prz):
            after = hi_or[t_prz[0]:]
            i1 = np.where(after >= tp1)[0]
            if len(i1):
                t_tp = int(t_prz[0] + i1[0])
                tp_hit = "TP2" if (after >= tp2).any() else "TP1"
        if t_tp is not None and (t_sl is None or t_tp < t_sl):
            status = "Selesai"
        elif t_sl is not None:
            status = "Gagal"
        elif len(t_prz):
            status = "Di PRZ"
        else:
            status = "Menuju PRZ"
        if d_locked and status == "Menuju PRZ":
            continue
        stats["aktif"] += 1

        cur = s * c[-1]
        dists = []
        for z in zones:
            if z["bot"] <= cur <= z["top"]:
                dists.append(0.0)
            else:
                edge = z["top"] if cur > z["top"] else z["bot"]
                dists.append(abs(cur - edge) / abs(cur) * 100)
        dist = np.nan if status == "Gagal" else min(dists)
        z_top = max(z["top"] for z in zones)
        z_bot = min(z["bot"] for z in zones)
        if cur > z_top:
            posisi = "Di atas PRZ" if s == 1 else "Di bawah PRZ"
        elif cur >= z_bot:
            posisi = "Di dalam PRZ"
        else:
            posisi = "Di bawah PRZ" if s == 1 else "Di atas PRZ"
        tembus = max(0.0, (z_bot - pmin) / abs(z_bot) * 100)

        ab_bars = int(B[0] - A[0])
        if d_locked:
            cd_bars, cd_jalan = int(piv[-1][0] - C[0]), False
        elif len(t_prz):
            cd_bars, cd_jalan = int(t_prz[0] + 1), False
        else:
            cd_bars, cd_jalan = int((n - 1) - C[0]), True
        if cd_jalan:
            waktu_lbl = "berjalan"
            waktu_txt = f"AB {ab_bars} hari · CD berjalan {cd_bars} hari"
        else:
            r_t = cd_bars / max(ab_bars, 1)
            waktu_lbl = ("CD terlalu cepat" if r_t < 0.5 else
                         "CD terlalu lambat" if r_t > 2 else "seimbang")
            waktu_txt = f"AB {ab_bars} hari · CD {cd_bars} hari → {waktu_lbl}"
        catatan = ""
        if status == "Selesai":
            catatan = f"{tp_hit} sudah tercapai"
        rr = (tp2 - entry) / (entry - sl_eff) if entry > sl_eff else np.nan
        risk_now = cur - sl_eff
        rr_now1 = (tp1 - cur) / risk_now if risk_now > 0 and tp1 > cur else np.nan
        rr_now2 = (tp2 - cur) / risk_now if risk_now > 0 and tp2 > cur else np.nan
        to_sl = -risk_now / abs(cur) * 100
        to_tp1 = (tp1 - cur) / abs(cur) * 100
        to_tp2 = (tp2 - cur) / abs(cur) * 100
        jebol = (chk_min - sl) / abs(sl) * 100

        def real(v):
            return s * v

        rz = []
        for z in zones:
            rz.append(dict(r=z["r"], bc_e=z["bc_e"],
                           xa_lvl=real(z["xa_lvl"]), bc_lvl=real(z["bc_lvl"]),
                           lo=min(real(z["top"]), real(z["bot"])),
                           hi=max(real(z["top"]), real(z["bot"]))))
        out.append(dict(
            pattern=name, arah="Bullish" if s == 1 else "Bearish", status=status,
            X=X, A=A, B=B, C=C, D=piv[-1] if d_locked else None, d_locked=d_locked,
            b_ratio=br, c_ratio=cr, zones=rz,
            entry=real(entry), sl=real(sl), sl_eff=real(sl_eff), tp1=real(tp1), tp2=real(tp2),
            jebol=jebol, stop_basis=stop_basis, buf_atr=buf_atr,
            rr=rr, dist=dist, age=age, price=float(c[-1]), touch_idx=touch_idx,
            tp_hit=tp_hit, catatan=catatan, posisi=posisi, tembus=tembus,
            waktu_lbl=waktu_lbl, waktu_txt=waktu_txt, rr_now1=rr_now1, rr_now2=rr_now2,
            to_sl=to_sl, to_tp1=to_tp1, to_tp2=to_tp2, pivots=piv, tent=tent,
        ))
        apply_ticks(out[-1], s)
    return out


def apply_ticks(p, s):
    up, dn = ("up", "down") if s == 1 else ("down", "up")
    p["entry"] = round_tick(p["entry"], up)
    p["tp1"] = round_tick(p["tp1"], dn)
    p["tp2"] = round_tick(p["tp2"], dn)
    p["sl"] = round_tick(p["sl"], dn)
    p["sl_eff"] = round_tick(p["sl_eff"], dn)
    cur = p["price"]
    risk_e = s * (p["entry"] - p["sl_eff"])
    p["rr"] = s * (p["tp2"] - p["entry"]) / risk_e if risk_e > 0 else np.nan
    risk_n = s * (cur - p["sl_eff"])
    r1, r2 = s * (p["tp1"] - cur), s * (p["tp2"] - cur)
    p["rr_now1"] = r1 / risk_n if risk_n > 0 and r1 > 0 else np.nan
    p["rr_now2"] = r2 / risk_n if risk_n > 0 and r2 > 0 else np.nan
    p["to_sl"] = (p["sl_eff"] / cur - 1) * 100
    p["to_tp1"] = (p["tp1"] / cur - 1) * 100
    p["to_tp2"] = (p["tp2"] / cur - 1) * 100


# =============================================================================
# 4. DATA
# =============================================================================
def _clean_index(d):
    idx = pd.to_datetime(d.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    d = d.copy()
    d.index = idx
    return d


@st.cache_data(ttl=900, show_spinner=False)
def load_all(codes, period="2y"):
    """Unduh semua emiten sekali (batch 100). Data mentah, belum dibuang baris volume nol."""
    data = {}
    if yf is None:
        return data
    codes = list(codes)
    for k in range(0, len(codes), 100):
        chunk = codes[k:k + 100]
        syms = [t + ".JK" for t in chunk]
        try:
            raw = yf.download(syms, period=period, interval="1d", group_by="ticker",
                              auto_adjust=False, threads=True, progress=False)
        except Exception:
            continue
        if raw is None or raw.empty:
            continue
        for t, sym in zip(chunk, syms):
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    if sym not in raw.columns.get_level_values(0):
                        continue
                    d = raw[sym]
                else:
                    d = raw
                d = d[["Open", "High", "Low", "Close", "Volume"]].dropna(how="all")
            except Exception:
                continue
            if d.empty:
                continue
            data[t] = _clean_index(d)
    return data


@st.cache_data(ttl=900, show_spinner=False)
def load_ihsg(period="2y"):
    if yf is None:
        return None
    try:
        d = yf.download("^JKSE", period=period, interval="1d", auto_adjust=False, progress=False)
    except Exception:
        return None
    if d is None or d.empty:
        return None
    close = d["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = close.dropna()
    close.index = _clean_index(close.to_frame()).index
    return close


def hb_frame(d):
    """Bentuk data persis seperti load_data Harmonic Board (buang NaN & volume nol)."""
    if d is None:
        return None
    d = d[["Open", "High", "Low", "Close", "Volume"]].dropna()
    d = d[d["Volume"] > 0]
    if len(d) < 80:
        return None
    return d


# =============================================================================
# 5. MODE PASAR & GERBANG IHSG
# =============================================================================
def gate_ihsg(close, perbaikan):
    """
    Gerbang BEAR Compounding.
    perbaikan=False : persis compounding_terminal.py (sekali terbuka, tidak menutup lagi).
    perbaikan=True  : begitu IHSG membuat dasar baru di dalam episode, gerbang MENUTUP lagi
                      dan baru terbuka kalau naik >=20% dari dasar baru itu.
    """
    roll = close.rolling(252, min_periods=50).max()
    dd = (close - roll) / roll
    in_ep, tr, tr_date, sig, reg = False, None, None, False, "NORMAL"
    for t in close.index:
        d = dd.loc[t]
        c = float(close.loc[t])
        if pd.isna(d):
            reg = "NORMAL"
            continue
        if not in_ep:
            if d <= HYSTERESIS_ENTER_BEAR:
                in_ep, tr, tr_date, sig, reg = True, c, t, False, "BEAR"
            else:
                reg = "NORMAL"
        else:
            if c < tr:
                tr, tr_date = c, t
                if perbaikan:
                    sig = False
            if c >= RECOVERY_DARI_TROUGH * tr:
                sig = True
            if d > HYSTERESIS_EXIT_BEAR:
                in_ep, sig, reg = False, False, "NORMAL"
            else:
                reg = "NORMAL" if sig else "BEAR"
    return dict(regime=reg, dd=float(dd.iloc[-1]) * 100, in_ep=in_ep, trough=tr,
                trough_date=tr_date,
                pct_trough=(float(close.iloc[-1]) / tr - 1) * 100 if in_ep and tr else None)


def market_mode(close):
    ret20 = float(close.iloc[-1] / close.iloc[-21] - 1)
    if ret20 <= PANIK_RET20:
        mode = "PANIK"
    elif ret20 > EUFORIA_RET20:
        mode = "EUFORIA"
    else:
        mode = "NORMAL"
    peak = float(close.tail(252).max())
    return dict(mode=mode, ret20=ret20 * 100, close=float(close.iloc[-1]),
                tanggal=close.index[-1], dd_peak=(float(close.iloc[-1]) / peak - 1) * 100,
                gate_lama=gate_ihsg(close, False), gate_baru=gate_ihsg(close, True))


# =============================================================================
# 6. SCAN HARMONIC (bullish, Besar + Menengah)
# =============================================================================
def enrich_signal(p, d, piv, lk):
    """Tambahan untuk menambal kelemahan Harmonic Board lama."""
    h = d["High"].values.astype(float)
    l = d["Low"].values.astype(float)
    c = d["Close"].values.astype(float)
    n = len(d)
    top = max(z["hi"] for z in p["zones"])
    bot = min(z["lo"] for z in p["zones"])
    top_o, bot_o = round_tick(top, "up"), round_tick(bot, "up")   # harga antri (sama dengan backtest)

    # hari C terkunci
    c_bar = p["C"][0]
    lock = None
    for k, q in enumerate(piv):
        if q[0] == c_bar and q[2] == p["C"][2]:
            lock = lk[k]
            break
    if lock is None:
        lock = c_bar + 1

    # sejak kapan sinyal aktif (jarak close ke PRZ pertama kali <= 15% setelah C terkunci)
    aktif_idx = None
    for i in range(lock, n):
        dist_i = 0.0 if c[i] <= top else (c[i] - top) / c[i] * 100
        if dist_i <= HB_MAX_DIST:
            aktif_idx = i
            break

    # pertama kali menyentuh PRZ (low <= batas atas PRZ) setelah C
    sentuh_idx = None
    lows = l[c_bar + 1:]
    hit = np.where(lows <= top)[0]
    if len(hit):
        sentuh_idx = int(c_bar + 1 + hit[0])

    risiko_atas = (top_o - p["sl_eff"]) / top_o * 100
    potensi_atas = (p["tp1"] - top_o) / top_o * 100
    lebar = potensi_atas <= 0 or risiko_atas > HB_LEBAR_X * potensi_atas
    return dict(top=top_o, bot=bot_o, lock_idx=lock,
                aktif_idx=aktif_idx, sentuh_idx=sentuh_idx,
                risiko_atas=risiko_atas, potensi_atas=potensi_atas, lebar=lebar)


@st.cache_data(ttl=900, show_spinner=False)
def scan_harmonic(codes):
    data = load_all(codes)
    rows, gagal = [], 0
    for t in HB_TICKERS:
        d = hb_frame(data.get(t))
        if d is None:
            continue
        val_min = float((d["Close"] * d["Volume"]).tail(20).min()) / 1e9
        h = d["High"].values.astype(float)
        l = d["Low"].values.astype(float)
        c = d["Close"].values.astype(float)
        atr = atr_wilder(h, l, c, 14)
        n = len(d)
        for skala, (mult, age) in HB_SCALES.items():
            try:
                pats = detect_patterns(d, 14, mult, age, None, "Close harian", 0.0)
                piv, lk = zigzag_locks(h, l, atr, mult)
            except Exception:
                gagal += 1
                continue
            for p in pats:
                if p["arah"] != "Bullish" or p["status"] not in ("Menuju PRZ", "Di PRZ"):
                    continue
                rr_plan = p["rr"] if p["status"] == "Menuju PRZ" else p["rr_now2"]
                ok_rr = pd.notna(rr_plan) and rr_plan >= HB_RR_MIN - 1e-9
                ok_val = val_min >= HB_VAL_MIN
                if not (ok_rr and ok_val):
                    continue
                e = enrich_signal(p, d, piv, lk)
                ok_dist = pd.notna(p["dist"]) and p["dist"] <= HB_MAX_DIST
                if ok_dist:
                    kategori = "SINYAL"
                elif e["aktif_idx"] is not None:
                    kategori = "PERNAH ≤15%"
                else:
                    continue
                last_dt = d.index[-1]
                aktif_dt = d.index[e["aktif_idx"]] if e["aktif_idx"] is not None else last_dt
                umur_sinyal = int((last_dt - aktif_dt).days)
                after_c = h[p["C"][0] + 1:]
                tembus_c = bool(len(after_c) and float(after_c.max()) > p["C"][1])
                sentuh_n = (n - 1 - e["sentuh_idx"]) if e["sentuh_idx"] is not None else None
                if tembus_c:
                    st_order = "BATAL (tembus C)"
                elif umur_sinyal > HB_UMUR_MAX:
                    st_order = "KEDALUWARSA"
                elif sentuh_n is not None and sentuh_n > HB_SENTUH_MAX:
                    st_order = "TUA"
                else:
                    st_order = "SAH"
                rows.append({
                    "Status Order": st_order, "Harga C": p["C"][1], "Umur sinyal (hari)": umur_sinyal,
                    "Kode": t, "Skala": skala, "Pola": p["pattern"], "Status": p["status"],
                    "Kategori": kategori, "Harga": p["price"], "Jarak PRZ %": p["dist"],
                    "Antri Atas": e["top"], "Antri Bawah": e["bot"],
                    "Stop (close)": p["sl_eff"], "TP1": p["tp1"], "TP2": p["tp2"],
                    "R:R Rencana": rr_plan,
                    "Sentuh PRZ (hari lalu)": (n - 1 - e["sentuh_idx"]) if e["sentuh_idx"] is not None else None,
                    "Aktif sejak": d.index[e["aktif_idx"]].strftime("%d %b %y") if e["aktif_idx"] is not None else "-",
                    "Hari aktif": (n - 1 - e["aktif_idx"]) if e["aktif_idx"] is not None else None,
                    "PRZ lebar": "⚠ YA" if e["lebar"] else "",
                    "Risiko dari atas %": -e["risiko_atas"],
                    "Potensi TP1 dari atas %": e["potensi_atas"],
                    "Waktu": p["waktu_txt"], "Umur C": p["age"],
                    "Tanggal C": d.index[p["C"][0]].strftime("%d %b %y"),
                    "Value Min 20H (M)": val_min,
                })
    return pd.DataFrame(rows), gagal


def min_hari_ke_prz(close, top, arb_pct):
    """Minimal berapa hari bursa harga bisa turun sampai batas atas PRZ kalau tiap hari kena ARB."""
    if close <= top:
        return 0
    arb = arb_pct / 100.0
    if arb <= 0 or arb >= 1:
        return None
    return int(math.ceil(math.log(top / close) / math.log(1 - arb) - 1e-9))


# =============================================================================
# 7. SCAN COMPOUNDING (logika analyze_stock asli, tanpa sizing)
# =============================================================================
def hitung_fase_wyckoff(low_series, min_retrace=0.05, min_margin=0.03):
    if len(low_series) < 60:
        return 0
    window = low_series.tail(LOOKBACK_FASE)
    gz_idx = window.values.argmin()
    gz_val = window.iloc[gz_idx]
    after = window.iloc[gz_idx:]
    if len(after) < 10:
        return 0
    phase = 0
    phase_high = after.iloc[0]
    in_retrace = False
    for val in after.iloc[1:]:
        if not in_retrace:
            if val > phase_high:
                phase_high = val
            elif val < phase_high * (1 - min_retrace):
                in_retrace = True
        else:
            if val > phase_high * (1 + min_margin):
                phase += 1
                phase_high = val
                in_retrace = False
    return max(phase, 1) if phase_high > gz_val else 0


def ara_pct(prev_close):
    if prev_close <= 200:
        return 0.35
    if prev_close <= 5000:
        return 0.25
    return 0.20


def ct_signal(df_stock):
    if df_stock is None or len(df_stock.dropna()) < 130:
        return None
    close = df_stock["Close"].dropna()
    high = df_stock["High"].dropna()
    low = df_stock["Low"].dropna()
    volume = df_stock["Volume"].dropna()
    idx = close.index.intersection(volume.index)
    close, high, low, volume = close[idx], high[idx], low[idx], volume[idx]
    if len(close) < 130:
        return None
    if volume.tail(5).sum() == 0:
        return None
    val_ma20 = (close * volume).rolling(20).mean().iloc[-1]
    hh20 = high.shift(1).rolling(LL_PERIOD).max().iloc[-1]
    ll20 = low.shift(1).rolling(LL_PERIOD).min().iloc[-1]
    close_now = close.iloc[-1]
    if pd.isna(hh20) or pd.isna(ll20) or ll20 <= 0:
        return None
    heartbeat = (hh20 - ll20) / ll20
    vma10 = volume.rolling(10).mean().iloc[-1]
    vma30 = volume.rolling(30).mean().iloc[-1]
    vol_ratio = vma10 / vma30 if vma30 > 0 else 999
    if val_ma20 < MIN_LIQUIDITY or heartbeat < MIN_HEARTBEAT or vol_ratio >= VOL_RATIO_MAX:
        return None
    if close_now < ll20 or close_now < hh20:
        return None
    ll10, hh10 = low.rolling(10).min(), high.rolling(10).max()
    stoch_k = (100 * ((close - ll10) / (hh10 - ll10))).rolling(5).mean()
    stoch_k_now = stoch_k.iloc[-1]
    if pd.isna(stoch_k_now):
        return None
    streak = 0
    for v in stoch_k.values[::-1]:
        if pd.notna(v) and v > 80:
            streak += 1
        else:
            break
    if 3 <= streak <= 4:
        return None
    fase = hitung_fase_wyckoff(low)
    momentum_score = min(60, stoch_k_now * 0.6)
    fase_score = 30 if fase >= 3 else (20 if fase in (1, 2) else 10)
    vol_score = max(0, (1.0 - vol_ratio)) * 10
    buy_conf = min(99, momentum_score + fase_score + vol_score)
    prev_close = float(close.iloc[-2])
    high_now = float(high.iloc[-1])
    kunci_ara = close_now >= prev_close * (1 + ara_pct(prev_close)) * 0.99 and close_now >= high_now
    llock = float(low.tail(20).min())   # CL yang dikunci saat beli (sama dengan form Beli app lama)
    return dict(close=float(close_now), ll20=float(ll20), hh20=float(hh20), stoch_k=float(stoch_k_now), llock=llock,
                vol_ratio=float(vol_ratio), fase=int(fase), buy_confidence=float(buy_conf),
                val_ma20=float(val_ma20) / 1e9, kunci_ara=bool(kunci_ara),
                chg=(float(close_now) / prev_close - 1) * 100)


@st.cache_data(ttl=900, show_spinner=False)
def scan_compounding(codes):
    data = load_all(codes)
    rows = []
    for t in CT_TICKERS:
        try:
            m = ct_signal(data.get(t))
        except Exception:
            m = None
        if m:
            m["ticker"] = t
            rows.append(m)
    return rows


def ct_table(rows, mm):
    ambang_lama = AMBANG_CONF_BEAR if mm["gate_lama"]["regime"] == "BEAR" else AMBANG_CONF_NORMAL
    ambang_baru = AMBANG_CONF_BEAR if mm["gate_baru"]["regime"] == "BEAR" else AMBANG_CONF_NORMAL
    out = []
    for m in rows:
        tampil_lama = m["buy_confidence"] >= ambang_lama
        if m["ticker"] in RED_FLAG:
            status = "Dicoret: red-flag"
        elif m["kunci_ara"]:
            status = "Dicoret: terkunci ARA"
        elif m["buy_confidence"] < ambang_baru:
            status = f"Dicoret: conf < {ambang_baru} (gerbang BEAR)"
        elif mm["mode"] == "EUFORIA":
            status = "Ditahan: rem euforia"
        else:
            status = "BELI"
        out.append({
            "Kode": m["ticker"], "Status": status, "Buy Conf": m["buy_confidence"],
            "Close": m["close"], "Naik hari ini %": m["chg"], "CL (LL20)": m["ll20"],
            "HH20": m["hh20"], "K": m["stoch_k"], "Fase": m["fase"], "Vol Ratio": m["vol_ratio"],
            "Value MA20 (M)": m["val_ma20"], "Tampil di app lama": "Ya" if tampil_lama else "Tidak",
        })
    df = pd.DataFrame(out)
    if not df.empty:
        df["_s"] = (df["Status"] != "BELI").astype(int)
        df = df.sort_values(["_s", "Buy Conf"], ascending=[True, False]).drop(columns="_s")
        df = df.reset_index(drop=True)
    return df, ambang_lama, ambang_baru



# =============================================================================
# 7b. GRAFIK POLA (disalin dari harmonic_board_app.py)
# =============================================================================
CHART_COL = dict(bg="#06080b", panel="#0b1016", grid="#141c25", text="#c9d4df",
                 green="#00ff9c", red="#ff4d6d", amber="#ffb000", cyan="#22d3ee",
                 violet="#a78bfa", dim="#4b5a6a")
CHART_FONT = "JetBrains Mono, Consolas, monospace"


def _base_layout(fig, df, start, x_end, title, title_color, nticks=7):
    xs = np.arange(start, len(df))
    step = max(1, len(xs) // nticks)
    tv = list(xs[step // 2::step])
    tt, prev_y = [], None
    for i in tv:
        d = df.index[i]
        lab = d.strftime("%d %b")
        if d.year != prev_y:
            lab += d.strftime(" '%y")
            prev_y = d.year
        tt.append(lab)
    fig.update_layout(
        template="plotly_dark", paper_bgcolor=CHART_COL["bg"], plot_bgcolor=CHART_COL["panel"],
        font=dict(family=CHART_FONT, color=CHART_COL["text"], size=12),
        height=620, margin=dict(l=8, r=8, t=44, b=8),
        title=dict(text=title, font=dict(color=title_color, size=15), x=0.01),
        xaxis=dict(rangeslider=dict(visible=False), tickvals=tv, ticktext=tt,
                   gridcolor=CHART_COL["grid"], range=[start - 2, x_end]),
        yaxis=dict(gridcolor=CHART_COL["grid"], side="right", tickformat=",.0f"),
        showlegend=False, hovermode="x unified", dragmode="pan",
    )


def _candles(fig, df, start):
    d = df.iloc[start:]
    xs = np.arange(start, len(df))
    fig.add_trace(go.Candlestick(
        x=xs, open=d["Open"], high=d["High"], low=d["Low"], close=d["Close"],
        increasing=dict(line=dict(color=CHART_COL["green"], width=1), fillcolor=CHART_COL["green"]),
        decreasing=dict(line=dict(color=CHART_COL["red"], width=1), fillcolor=CHART_COL["red"]),
        hovertext=list(d.index.strftime("%d %b %Y")), hoverinfo="text+y", name="Harga",
    ))


def _zigzag(fig, pivots, tent, start):
    zz = [q for q in pivots if q[0] >= start]
    if tent and tent[0] >= start:
        zz = zz + [tent]
    if zz:
        fig.add_trace(go.Scatter(x=[q[0] for q in zz], y=[q[1] for q in zz], mode="lines",
                                 line=dict(color=CHART_COL["dim"], width=1, dash="dot"), hoverinfo="skip"))


def make_chart(code, df, p, scale_txt="", compact=True):
    n = len(df)
    proj = 20 if compact else 30
    start = max(0, (p["B"][0] - 10) if compact else (p["X"][0] - 30))
    x1 = n - 1 + proj
    bull = p["arah"] == "Bullish"
    accent = CHART_COL["cyan"] if bull else CHART_COL["amber"]
    fill = "rgba(34,211,238,0.13)" if bull else "rgba(255,176,0,0.13)"
    fig = go.Figure()
    _candles(fig, df, start)
    _zigzag(fig, p["pivots"], p["tent"], start)
    X, A, B, C = p["X"], p["A"], p["B"], p["C"]
    if p["D"] is not None:
        D, d_dash = (p["D"][0], p["D"][1]), "solid"
    elif p.get("touch_idx") is not None:
        D, d_dash = (p["touch_idx"], p["entry"]), "solid"
    else:
        D, d_dash = (n - 1 + proj // 3, p["entry"]), "dash"
    for pts in ([X, A, B], [B, C, D]):
        fig.add_trace(go.Scatter(x=[q[0] for q in pts] + [pts[0][0]], y=[q[1] for q in pts] + [pts[0][1]],
                                 fill="toself", fillcolor=fill, line=dict(width=0), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[X[0], A[0], B[0], C[0]], y=[X[1], A[1], B[1], C[1]], mode="lines+markers",
                             line=dict(color=accent, width=2), marker=dict(size=7, color=accent), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[C[0], D[0]], y=[C[1], D[1]], mode="lines",
                             line=dict(color=accent, width=2, dash=d_dash), hoverinfo="skip"))
    for lab, q in zip("XABCD", [X, A, B, C, D]):
        if q[0] < start:
            continue
        is_low = (lab in "XBD") if bull else (lab in "AC")
        fig.add_annotation(x=q[0], y=q[1], text=f"<b>{lab}</b>", showarrow=False,
                           yshift=-16 if is_low else 16, font=dict(color=CHART_COL["text"], size=14))
    zone_fill = ["rgba(167,139,250,0.30)", "rgba(167,139,250,0.15)"]
    printed = []
    for k, z in enumerate(p["zones"]):
        x0 = C[0] + (D[0] - C[0]) // 2
        mid = (z["lo"] + z["hi"]) / 2
        half = max((z["hi"] - z["lo"]) / 2, abs(mid) * 0.006)
        y0v, y1v = mid - half, mid + half
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0v, y1=y1v,
                      fillcolor=zone_fill[min(k, 1)], line=dict(color=CHART_COL["violet"], width=1))
        if k == 0:
            fig.add_annotation(x=x0, y=y1v, xanchor="left", yanchor="bottom", showarrow=False,
                               text=f"PRZ {z['r']}", font=dict(color=CHART_COL["violet"], size=11),
                               bgcolor="rgba(6,8,11,0.75)")
        for v_, yv, anc in ((z["hi"], y1v, "bottom"), (z["lo"], y0v, "top")):
            if any(abs(v_ - w) / max(abs(w), 1e-9) < 0.005 for w in printed):
                continue
            printed.append(v_)
            fig.add_annotation(x=x1, y=yv, xanchor="right", yanchor=anc, showarrow=False,
                               text=f"({v_:,.0f})", font=dict(color=CHART_COL["violet"], size=11))
    lines = [(p["sl"], "STOP POLA", CHART_COL["red"]), (p["tp1"], "TP1", CHART_COL["green"]),
             (p["tp2"], "TP2", CHART_COL["green"])]
    if p["status"] == "Menuju PRZ":
        lines.append((C[1], "INVALID", CHART_COL["amber"]))
    for lvl, lab, colr in lines:
        fig.add_shape(type="line", x0=C[0], x1=x1, y0=lvl, y1=lvl, line=dict(color=colr, width=1, dash="dash"))
        fig.add_annotation(x=x1, y=lvl, xanchor="right", yanchor="bottom", showarrow=False,
                           text=f"{lab} ({lvl:,.0f})", font=dict(color=colr, size=11), bgcolor="rgba(6,8,11,0.7)")
    last_px = float(df["Close"].iloc[-1])
    fig.add_shape(type="line", x0=start, x1=x1, y0=last_px, y1=last_px,
                  line=dict(color="#ffffff", width=1.2, dash="dot"))
    fig.add_annotation(x=start, y=last_px, xanchor="left", yanchor="bottom", showarrow=False,
                       text=f"<b>HARGA {last_px:,.0f}</b>", font=dict(color="#000", size=11), bgcolor="#ffffff")
    tx = min(x1 - 2, D[0] + proj // 2)
    fig.add_annotation(x=tx, y=p["tp2"], ax=D[0], ay=D[1], xref="x", yref="y", axref="x", ayref="y",
                       showarrow=True, arrowhead=3, arrowsize=1.2, arrowwidth=1.5,
                       arrowcolor=CHART_COL["green"], text="")
    title = f"{code} · {p['pattern']} · {p['status']}" + (f" · {scale_txt}" if scale_txt else "")
    _base_layout(fig, df, start, x1 + 2, title, accent, nticks=4 if compact else 7)
    if compact:
        fig.update_layout(height=460, title=dict(font=dict(size=12)), margin=dict(l=4, r=4, t=36, b=4))
    return fig


def find_pattern(d, skala, pola, tgl_c):
    mult, age = HB_SCALES[skala]
    for p in detect_patterns(d, 14, mult, age, None, "Close harian", 0.0):
        if (p["arah"] == "Bullish" and p["pattern"] == pola
                and d.index[p["C"][0]].strftime("%d %b %y") == tgl_c):
            return p
    return None


# =============================================================================
# 8. STATE, CEK POSISI & ALOKASI
# =============================================================================
AKUN = ["OBERLIN", "TEKNIKAL"]
ASAL = ["compounding", "harmonic_besar", "harmonic_menengah", "warisan", "deviasi"]
POS_COLS = ["akun", "kode", "asal", "lot", "avg", "tanggal_beli", "ll20", "ob_streak", "ob_tgl",
            "tp1", "stop", "harga_c", "order_tp", "order_sl", "catatan"]
Q_COLS = ["akun", "kode", "asal", "bagian", "harga", "lot", "tanggal_pasang", "tp1", "stop",
          "harga_c", "catatan"]
NUM_POS = ["lot", "avg", "ll20", "ob_streak", "tp1", "stop", "harga_c"]
NUM_Q = ["harga", "lot", "tp1", "stop", "harga_c"]


def to_frame(records, cols, num_cols):
    df = pd.DataFrame(records if records else [], columns=cols)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols].copy()
    for c in cols:
        if c in num_cols:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
        else:
            df[c] = df[c].fillna("").astype(str).replace({"nan": "", "None": ""})
    df["kode"] = df["kode"].str.upper().str.replace(".JK", "", regex=False).str.strip()
    return df.reset_index(drop=True)


def clean_records(df):
    out = []
    for r in df.to_dict("records"):
        rr = {}
        for k, v in r.items():
            if isinstance(v, (float, np.floating)):
                rr[k] = None if np.isnan(v) else float(v)
            elif isinstance(v, (np.integer,)):
                rr[k] = int(v)
            else:
                rr[k] = v
        out.append(rr)
    return out


def num(v, default=0.0):
    try:
        v = float(v)
        return default if np.isnan(v) else v
    except Exception:
        return default


def to_ts(s):
    try:
        if s is None or str(s).strip() == "":
            return None
        return pd.Timestamp(str(s)[:10])
    except Exception:
        return None


def parse_orders(text):
    """'476@790, 471@820' -> [(476, 790), (471, 820)]. Titik ribuan diabaikan."""
    out = []
    for part in str(text or "").replace(";", ",").split(","):
        part = part.strip().replace(" ", "").replace(".", "")
        if "@" not in part:
            continue
        a, b = part.split("@", 1)
        try:
            out.append((int(float(a)), float(b)))
        except Exception:
            continue
    return out


def import_ct_json(js):
    """portfolio.json Compounding Terminal -> baris posisi akun TEKNIKAL."""
    rows = []
    for p in js.get("positions", []):
        rows.append(dict(
            akun="TEKNIKAL", kode=str(p.get("ticker", "")).upper(),
            asal="compounding" if p.get("asal", "compounding") == "compounding" else "warisan",
            lot=p.get("lots"), avg=p.get("entry_price"), tanggal_beli=p.get("tanggal_beli") or "",
            ll20=p.get("ll20_terkunci"), ob_streak=p.get("ob_streak", 0),
            ob_tgl=p.get("last_ob_check") or "", tp1=None, stop=None, harga_c=None,
            order_tp="", order_sl="", catatan="impor Compounding Terminal"))
    return rows, float(js.get("current_cash", 0) or 0), float(
        js.get("total_modal_masuk", js.get("initial_capital", 0)) or 0)


def series_of(d):
    c = d["Close"].dropna()
    h = d["High"].reindex(c.index)
    l = d["Low"].reindex(c.index)
    return c, h, l


def eval_ct_position(r, d):
    """ob_streak dihitung per candle (hari yang terlewat tetap terhitung). Urutan sama dengan backtest."""
    c, h, l = series_of(d)
    K = (100 * (c - l.rolling(10).min()) / (h.rolling(10).max() - l.rolling(10).min())).rolling(5).mean()
    tb, obt = to_ts(r["tanggal_beli"]), to_ts(r["ob_tgl"])
    ob = int(num(r["ob_streak"]))
    ll, avg = num(r["ll20"]), num(r["avg"])
    if obt is not None:
        todo = [t for t in c.index if t > obt]
    elif tb is not None:
        todo = [t for t in c.index if t >= tb]
    else:
        todo = list(c.index[-1:])
    trig = None
    for t in todo:
        k = K.get(t, np.nan)
        if tb is not None and t <= tb:          # hari beli: hanya catat streak, tanpa exit
            ob = 1 if (pd.notna(k) and k > 80) else 0
            obt = t
            continue
        if ll > 0 and c[t] < ll:
            trig, obt = ("CL (close < LL20)", t), t
            ob = 0
            break
        ob = ob + 1 if (pd.notna(k) and k > 80) else 0
        obt = t
        if ob >= 2:
            trig = ("K>80 dua hari", t)
            break
        if ob >= 1 and avg > 0 and l[t] <= avg:
            trig = ("pengaman breakeven", t)
            break
    return dict(ob=ob, ob_tgl=obt.strftime("%Y-%m-%d") if obt is not None else "",
                trig=trig, k=float(K.iloc[-1]) if pd.notna(K.iloc[-1]) else None)


def eval_hb_position(r, d):
    c, h, l = series_of(d)
    tb = to_ts(r["tanggal_beli"])
    tp1, stop = num(r["tp1"]), num(r["stop"])
    idx = [t for t in c.index if tb is None or t > tb]
    for t in idx:
        if tp1 > 0 and h[t] >= tp1:
            return ("TP1 tersentuh", t)
        if stop > 0 and c[t] < stop:
            return ("close di bawah stop", t)
    return None


def eval_queue(r, d, last_dt):
    c, h, l = series_of(d)
    tp = to_ts(r["tanggal_pasang"])
    harga, cpx = num(r["harga"]), num(r["harga_c"])
    idx = [t for t in c.index if tp is None or t > tp]
    for t in idx:
        if harga > 0 and l[t] <= harga:
            return ("TERISI?", t)
        if cpx > 0 and h[t] > cpx:
            return ("CABUT: tembus C", t)
    if tp is not None and (last_dt - tp).days > HB_UMUR_MAX:
        return ("CABUT: lewat 220 hari", last_dt)
    return None


def lot_hb(dana, harga):
    if harga <= 0:
        return 0
    return int(dana // (harga * 100 * (1 + FEE_BELI)))


def sesi_info(now):
    hm = (now.hour, now.minute)
    if now.weekday() >= 5:
        return "LIBUR", "Bursa tutup. Data = close hari bursa terakhir."
    if hm < (15, 0):
        return "PAGI", "Data belum representatif. Jangan ambil keputusan sekarang."
    if hm < (16, 15):
        return "SESI COMPOUNDING", "Candle hari ini masih berjalan. Ambil sinyal Compounding, beli sebelum close."
    return "SESI SORE", "Data final. Harmonic, cek posisi, antrian, dan rekap."


@st.cache_data(ttl=900, show_spinner=False)
def ihsg_history_fallback():
    try:
        d = yf.Ticker("^JKSE").history(period="10d", interval="1d", auto_adjust=False)
        if d is None or d.empty:
            return None
        s = d["Close"].dropna()
        idx = pd.to_datetime(s.index)
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        s.index = idx.normalize()
        return s
    except Exception:
        return None


def ihsg_fixed(close, stock_last):
    if close.index[-1] >= stock_last:
        return close, False
    fb = ihsg_history_fallback()
    if fb is not None:
        add = fb[fb.index > close.index[-1]]
        if len(add):
            close = pd.concat([close, add]).sort_index()
            close = close[~close.index.duplicated(keep="last")]
    return close, close.index[-1] < stock_last


# =============================================================================
# 9. ANTARMUKA
# =============================================================================
st.set_page_config(page_title="Mesin Gabungan", page_icon="◆", layout="wide")

COL = dict(bg="#06080b", panel="#0b1016", text="#c9d4df", green="#00ff9c", red="#ff4d6d",
           amber="#ffb000", cyan="#22d3ee", violet="#a78bfa", dim="#4b5a6a")
MODE_COL = {"PANIK": COL["red"], "NORMAL": COL["green"], "EUFORIA": COL["amber"]}

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;800&display=swap');
.stApp {{ background: radial-gradient(1200px 600px at 10% -10%, #0e1a14 0%, {COL['bg']} 55%); }}
.stApp, .stMarkdown, p, label, input, button, h1, h2, h3, h4 {{
  font-family: 'JetBrains Mono', Consolas, monospace !important; }}
.mg-head {{ border:1px solid #1a2430; border-left:4px solid {COL['green']};
  background:linear-gradient(90deg, rgba(0,255,156,0.06), rgba(0,0,0,0));
  padding:12px 16px; margin-bottom:12px; }}
.mg-title {{ color:{COL['green']}; font-size:24px; font-weight:800; letter-spacing:2px; }}
.mg-sub {{ color:{COL['dim']}; font-size:12px; letter-spacing:1px; }}
.mg-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:12px; }}
.mg-card {{ border:1px solid #1a2430; background:{COL['panel']}; padding:10px 14px; }}
.mg-card .k {{ color:{COL['dim']}; font-size:11px; letter-spacing:1px; }}
.mg-card .v {{ font-size:22px; font-weight:800; }}
.mg-card .s {{ color:{COL['dim']}; font-size:11px; margin-top:2px; }}
.mg-warn {{ border:1px solid #2a1f10; border-left:3px solid {COL['amber']}; background:#0f0c07;
  padding:10px 14px; color:{COL['text']}; font-size:13px; margin:6px 0 10px 0; }}
.mg-err {{ border:1px solid #2a1016; border-left:3px solid {COL['red']}; background:#12070a;
  padding:10px 14px; color:{COL['text']}; font-size:13px; margin:6px 0 10px 0; }}
.mg-act {{ background:{COL['panel']}; border:1px solid #1a2430; padding:10px 14px; margin:0 0 8px 0;
  font-size:15px; line-height:1.55; color:{COL['text']}; }}
.mg-act .t {{ display:flex; justify-content:space-between; align-items:center; }}
.mg-act .t .k {{ font-weight:800; color:#ffffff; font-size:19px; }}
.mg-act .t .b {{ font-size:12px; font-weight:800; border:1px solid; padding:2px 8px; letter-spacing:1px; }}
.mg-act .a {{ color:{COL['dim']}; font-size:12px; letter-spacing:1px; }}
.mg-act .n {{ color:{COL['dim']}; font-size:13px; margin-top:2px; }}
.mg-strip {{ display:flex; flex-wrap:wrap; gap:6px 14px; font-size:12px; color:{COL['dim']};
  border:1px solid #1a2430; background:{COL['panel']}; padding:8px 12px; margin-bottom:10px; }}
.mg-strip b {{ color:{COL['text']}; }}
.mg-bar {{ background:#22252B; height:4px; margin-top:4px; }}
.mg-bar div {{ height:100%; }}
.mg-move {{ border:1px solid #10202a; border-left:4px solid {COL['cyan']}; background:#06121a;
  padding:12px 16px; color:{COL['text']}; font-size:15px; margin:6px 0 12px 0; }}
@media (max-width: 640px) {{
  .mg-grid {{ grid-template-columns:repeat(2,1fr); }} .mg-card .v {{ font-size:18px; }}
  .mg-title {{ font-size:18px; }} }}
div.stButton > button {{ background:#0d1a14; color:{COL['green']}; border:1px solid {COL['green']};
  border-radius:2px; letter-spacing:1px; }}
div.stButton > button:hover {{ background:{COL['green']}; color:#000; }}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="mg-head">
  <div class="mg-title">◆ MESIN GABUNGAN</div>
  <div class="mg-sub">TAHAP 2 // MODE PASAR · ALOKASI KAS · DAFTAR ORDER · STATE JSON</div>
</div>""", unsafe_allow_html=True)

if yf is None:
    st.error("Paket yfinance belum terpasang. Jalankan: pip install yfinance")
    st.stop()


def cards(items):
    html = '<div class="mg-grid">'
    for k, v, c, s in items:
        html += (f'<div class="mg-card" style="border-left:3px solid {c}"><div class="k">{k}</div>'
                 f'<div class="v" style="color:{c}">{v}</div><div class="s">{s}</div></div>')
    return html + "</div>"


def rp(v):
    return f"{v:,.0f}".replace(",", ".")


# ---------------- state sesi ----------------
ss = st.session_state
ss.setdefault("ver", 0)
ss.setdefault("pos_base", to_frame([], POS_COLS, NUM_POS))
ss.setdefault("q_base", to_frame([], Q_COLS, NUM_Q))
ss.setdefault("meta", {"kas_OBERLIN": 0.0, "kas_TEKNIKAL": 0.0, "kas_settle": 0.0, "modal_masuk": 0.0})
ss.setdefault("_up_sig", None)
ss.setdefault("_ct_sig", None)

# State otomatis: kalau sesi baru dan ada file state_gabungan.json di repo, langsung dimuat.
STATE_REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state_gabungan.json")
if not ss.get("_auto_loaded"):
    ss["_auto_loaded"] = True
    ss["_auto_src"] = None
    if os.path.exists(STATE_REPO):
        try:
            with open(STATE_REPO, encoding="utf-8") as f:
                js0 = json.load(f)
            ss["pos_base"] = to_frame(js0.get("posisi", []), POS_COLS, NUM_POS)
            ss["q_base"] = to_frame(js0.get("antrian", []), Q_COLS, NUM_Q)
            kas0 = js0.get("kas", {})
            ss["meta"] = {"kas_OBERLIN": float(kas0.get("OBERLIN", 0) or 0),
                          "kas_TEKNIKAL": float(kas0.get("TEKNIKAL", 0) or 0),
                          "kas_settle": float(js0.get("kas_settle_teknikal", kas0.get("TEKNIKAL", 0)) or 0),
                          "modal_masuk": float(js0.get("modal_masuk_teknikal", 0) or 0)}
            ss["_auto_src"] = js0.get("disimpan", "?")
            ss["ver"] += 1
        except Exception:
            ss["_auto_src"] = "GAGAL"

with st.sidebar:
    st.markdown("### ▌PARAMETER")
    basis_opt = st.radio("Dasar porsi harmonic (10% + 10%)",
                         ["Ekuitas OBERLIN + TEKNIKAL", "Ekuitas OBERLIN saja"],
                         help="Backtest memakai kas bersama, jadi dasarnya ekuitas gabungan. "
                              "Saat PANIK, kekurangan kas OBERLIN ditutup lewat saran pindah kas.")
    arb = st.number_input("Batas ARB harian (%)", 1.0, 35.0, ARB_DEFAULT, 0.5,
                          help="ARB asimetris 7% berlaku 19 Okt s.d. 31 Des 2026.")
    if st.button("▶ TARIK ULANG DATA", width="stretch"):
        load_all.clear()
        load_ihsg.clear()
        ihsg_history_fallback.clear()
        scan_harmonic.clear()
        scan_compounding.clear()
        st.rerun()
    st.caption(f"Universe {len(ALL_TICKERS)} kode. Data Yahoo 2 tahun, cache 15 menit.")

now = datetime.now(WIB)
sesi, sesi_txt = sesi_info(now)

with st.spinner(f"Menarik data {len(ALL_TICKERS)} emiten & memindai... (bisa 2-4 menit)"):
    data_all = load_all(ALL_TICKERS)
    hb_df, hb_gagal = scan_harmonic(ALL_TICKERS)
    ct_rows = scan_compounding(ALL_TICKERS)
if not data_all:
    st.error("Data saham gagal ditarik. Coba tarik ulang beberapa menit lagi.")
    st.stop()
stock_last = pd.Series([d.index[-1] for d in data_all.values()]).mode().iloc[0]
ihsg_raw = load_ihsg()
if ihsg_raw is None or len(ihsg_raw) < 260:
    st.error("Data IHSG (^JKSE) gagal ditarik. Coba tarik ulang beberapa menit lagi.")
    st.stop()
ihsg, ihsg_telat = ihsg_fixed(ihsg_raw, stock_last)
mm = market_mode(ihsg)

_sc = COL["cyan"] if sesi.startswith("SESI") else COL["amber"]
_ic = COL["red"] if ihsg_telat else COL["text"]
st.markdown(f'<div class="mg-strip"><span><b style="color:{_sc}">{sesi}</b></span>'
            f'<span>saham <b>{stock_last.strftime("%d %b")}</b></span>'
            f'<span>IHSG <b style="color:{_ic}">{mm["tanggal"].strftime("%d %b")}</b></span>'
            f'<span>dibuka <b>{now.strftime("%d %b %H:%M")}</b></span>'
            f'<span>{len(data_all)} emiten</span></div>', unsafe_allow_html=True)
st.caption(sesi_txt)
if ihsg_telat:
    st.markdown(f'<div class="mg-err"><b>Mode pasar memakai IHSG tanggal {mm["tanggal"].strftime("%d %b %Y")}</b>, '
                f'sedangkan data saham sudah {stock_last.strftime("%d %b %Y")}. Yahoo belum memperbarui ^JKSE. '
                'Kalau IHSG sedang dekat batas -5% / +10%, cek angka IHSG manual sebelum memutuskan.</div>',
                unsafe_allow_html=True)

tab_ring, tab_aksi, tab_state, tab_hb, tab_ct = st.tabs(
    ["RINGKAS", "AKSI", "STATE", "HARMONIC", "COMPOUND"])

# ----------------------------------------------------------------- STATE (dibaca lebih dulu)
with tab_state:
    src0 = ss.get("_auto_src")
    if src0 and src0 != "GAGAL":
        st.success(f"State otomatis dimuat dari state_gabungan.json di repo (disimpan {src0}).")
    elif src0 == "GAGAL":
        st.error("state_gabungan.json di repo ada, tapi isinya tidak terbaca.")
    st.markdown("**1. Muat state** (opsional, untuk mengganti state otomatis dengan yang lebih baru)")
    c1, c2 = st.columns(2)
    up = c1.file_uploader("State dashboard (state_gabungan_*.json)", type="json", key="up_state")
    if up is not None and ss["_up_sig"] != (up.name, up.size):
        try:
            js = json.loads(up.getvalue().decode("utf-8"))
            ss["pos_base"] = to_frame(js.get("posisi", []), POS_COLS, NUM_POS)
            ss["q_base"] = to_frame(js.get("antrian", []), Q_COLS, NUM_Q)
            kas = js.get("kas", {})
            ss["meta"] = {"kas_OBERLIN": float(kas.get("OBERLIN", 0) or 0),
                          "kas_TEKNIKAL": float(kas.get("TEKNIKAL", 0) or 0),
                          "kas_settle": float(js.get("kas_settle_teknikal", kas.get("TEKNIKAL", 0)) or 0),
                          "modal_masuk": float(js.get("modal_masuk_teknikal", 0) or 0)}
            ss["_up_sig"] = (up.name, up.size)
            ss["ver"] += 1
            st.rerun()
        except Exception as ex:
            st.error(f"File state tidak valid: {ex}")
    upc = c2.file_uploader("Impor portfolio.json Compounding Terminal → TEKNIKAL", type="json", key="up_ct")
    if upc is not None and ss["_ct_sig"] != (upc.name, upc.size):
        try:
            js = json.loads(upc.getvalue().decode("utf-8"))
            rows, kas_ct, modal_ct = import_ct_json(js)
            base = ss["pos_base"]
            base = base[base["akun"] != "TEKNIKAL"]
            ss["pos_base"] = to_frame(clean_records(base) + rows, POS_COLS, NUM_POS)
            ss["meta"]["kas_TEKNIKAL"] = kas_ct
            ss["meta"]["kas_settle"] = kas_ct
            ss["meta"]["modal_masuk"] = modal_ct
            ss["_ct_sig"] = (upc.name, upc.size)
            ss["ver"] += 1
            st.rerun()
        except Exception as ex:
            st.error(f"portfolio.json tidak valid: {ex}")
    st.caption("Impor mengganti semua posisi TEKNIKAL dengan isi portfolio.json, mengisi kas TEKNIKAL dan "
               "Total Modal Masuk. Posisi insting (GOTO, HRUM) ubah asalnya jadi 'deviasi' di tabel.")

    st.markdown("**2. Kas tersedia (samakan dengan Trading Balance Stockbit, sudah dikurangi antrian ACTIVE)**")
    v = ss["ver"]
    k1, k2, k4, k3 = st.columns(4)
    kas_ob = k1.number_input("Kas OBERLIN (Rp)", 0.0, 1e12, float(ss["meta"]["kas_OBERLIN"]), 100_000.0,
                             format="%.0f", key=f"kas_ob_{v}")
    kas_tk = k2.number_input("Kas TEKNIKAL (Rp)", 0.0, 1e12, float(ss["meta"]["kas_TEKNIKAL"]), 100_000.0,
                             format="%.0f", key=f"kas_tk_{v}")
    kas_settle = k4.number_input("Kas TEKNIKAL sudah settle (Rp)", 0.0, 1e12,
                                 float(min(ss["meta"].get("kas_settle", kas_tk), kas_tk)), 100_000.0,
                                 format="%.0f", key=f"kas_st_{v}",
                                 help="Bagian kas yang boleh ditransfer ke sub-akun lain (hasil jual sudah lewat T+2).")
    kas_settle = min(kas_settle, kas_tk)
    modal_masuk = k3.number_input("Total Modal Masuk TEKNIKAL (Rp)", 0.0, 1e12, float(ss["meta"]["modal_masuk"]),
                                  1_000_000.0, format="%.0f", key=f"mm_{v}",
                                  help="Dasar sizing Compounding 20% per posisi, sama dengan app lama.")
    ss["meta"] = {"kas_OBERLIN": kas_ob, "kas_TEKNIKAL": kas_tk, "kas_settle": kas_settle,
                  "modal_masuk": modal_masuk}

    st.markdown("**3. Posisi** (tambah/hapus baris langsung di tabel; kolom teknis ada di ujung kanan)")
    pos_df = st.data_editor(
        ss["pos_base"], key=f"ed_pos_{v}", num_rows="dynamic", hide_index=True, width="stretch",
        column_order=["akun", "kode", "asal", "lot", "avg", "tp1", "stop", "order_tp", "order_sl",
                      "tanggal_beli", "harga_c", "ll20", "ob_streak", "ob_tgl", "catatan"],
        column_config={
            "akun": st.column_config.SelectboxColumn(options=AKUN, required=True),
            "asal": st.column_config.SelectboxColumn(options=ASAL, required=True),
            "lot": st.column_config.NumberColumn(format="%d"),
            "avg": st.column_config.NumberColumn(format="%.2f"),
            "tanggal_beli": st.column_config.TextColumn(help="YYYY-MM-DD"),
            "ll20": st.column_config.NumberColumn("LL20 kunci", format="%.0f", help="Compounding: CL"),
            "ob_streak": st.column_config.NumberColumn(format="%d", help="Diisi otomatis, jangan diubah"),
            "ob_tgl": st.column_config.TextColumn(help="Candle terakhir yang dihitung, otomatis"),
            "tp1": st.column_config.NumberColumn(format="%.0f", help="Harmonic: TP1"),
            "stop": st.column_config.NumberColumn(format="%.0f", help="Harmonic: stop basis close"),
            "harga_c": st.column_config.NumberColumn(format="%.0f", help="Harmonic: harga titik C"),
            "order_tp": st.column_config.TextColumn(help="Order TP terpasang, contoh 476@790, 471@820"),
            "order_sl": st.column_config.TextColumn(help="Order SL terpasang, contoh 947@635"),
        })
    st.markdown("**4. Antrian beli harmonic terpasang**")
    q_df = st.data_editor(
        ss["q_base"], key=f"ed_q_{v}", num_rows="dynamic", hide_index=True, width="stretch",
        column_config={
            "akun": st.column_config.SelectboxColumn(options=AKUN, required=True),
            "asal": st.column_config.SelectboxColumn(options=ASAL, required=True),
            "bagian": st.column_config.SelectboxColumn(options=["atas", "bawah", "gabung"]),
            "harga": st.column_config.NumberColumn(format="%.0f"),
            "lot": st.column_config.NumberColumn(format="%d"),
            "tanggal_pasang": st.column_config.TextColumn(help="YYYY-MM-DD"),
            "tp1": st.column_config.NumberColumn(format="%.0f"),
            "stop": st.column_config.NumberColumn(format="%.0f"),
            "harga_c": st.column_config.NumberColumn(format="%.0f"),
        })
    pos_df = to_frame(clean_records(pos_df), POS_COLS, NUM_POS)
    q_df = to_frame(clean_records(q_df), Q_COLS, NUM_Q)
    pos_df = pos_df[pos_df["kode"] != ""].reset_index(drop=True)
    q_df = q_df[q_df["kode"] != ""].reset_index(drop=True)


# ----------------------------------------------------------------- data posisi di luar universe
@st.cache_data(ttl=900, show_spinner=False)
def load_extra(codes):
    return load_all(codes, period="2y") if codes else {}


need = sorted(set(pos_df["kode"]).union(set(q_df["kode"])) - set(data_all))
extra = load_extra(tuple(need)) if need else {}


def get_df(k):
    return data_all.get(k) if k in data_all else extra.get(k)


def last_close(k, default):
    d = get_df(k)
    if d is None or d["Close"].dropna().empty:
        return default
    return float(d["Close"].dropna().iloc[-1])


# ----------------------------------------------------------------- cek posisi
aksi = []          # dict(urut, akun, aksi, kode, lot, harga, nilai, tp, sl, alasan)
pos_eval = {}      # index -> hasil (ob update)
mv = {"OBERLIN": 0.0, "TEKNIKAL": 0.0}
selesai_hb = set()  # (akun, kode) posisi harmonic yang sudah TP1/stop -> antrian saudara dicabut
for i, r in pos_df.iterrows():
    d = get_df(r["kode"])
    lot, avg = num(r["lot"]), num(r["avg"])
    px = last_close(r["kode"], avg)
    mv[r["akun"]] = mv.get(r["akun"], 0.0) + lot * 100 * px
    if d is None:
        aksi.append(dict(urut=9, akun=r["akun"], aksi="CEK DATA", kode=r["kode"], lot=lot, harga=None,
                         nilai=None, tp="", sl="", alasan="data Yahoo tidak tersedia"))
        continue
    if r["asal"] == "compounding":
        e = eval_ct_position(r, d)
        pos_eval[i] = e
        if num(r["ll20"]) <= 0:
            aksi.append(dict(urut=8, akun=r["akun"], aksi="LENGKAPI", kode=r["kode"], lot=lot, harga=None,
                             nilai=None, tp="", sl="", alasan="LL20 terkunci belum diisi, CL tidak bisa dicek"))
        if e["trig"]:
            hasil = "untung" if px > avg else "rugi"
            aksi.append(dict(urut=1, akun=r["akun"], aksi="JUAL", kode=r["kode"], lot=lot, harga=px,
                             nilai=lot * 100 * px, tp="", sl="",
                             alasan=f"Compounding: {e['trig'][0]} ({e['trig'][1].strftime('%d %b')}), {hasil}"))
    elif r["asal"] in ("harmonic_besar", "harmonic_menengah"):
        trg = eval_hb_position(r, d)
        if num(r["tp1"]) <= 0 or num(r["stop"]) <= 0:
            aksi.append(dict(urut=8, akun=r["akun"], aksi="LENGKAPI", kode=r["kode"], lot=lot, harga=None,
                             nilai=None, tp="", sl="", alasan="TP1/stop pola belum diisi"))
        if trg:
            selesai_hb.add((r["akun"], r["kode"]))
            if trg[0] == "TP1 tersentuh":
                aksi.append(dict(urut=1, akun=r["akun"], aksi="CEK TP1", kode=r["kode"], lot=lot,
                                 harga=num(r["tp1"]), nilai=None, tp="", sl="",
                                 alasan=f"TP1 tersentuh {trg[1].strftime('%d %b')}: pastikan terjual semua"))
            else:
                aksi.append(dict(urut=1, akun=r["akun"], aksi="JUAL", kode=r["kode"], lot=lot, harga=px,
                                 nilai=lot * 100 * px, tp="", sl="",
                                 alasan=f"close {rp(px)} di bawah stop {rp(num(r['stop']))} ({trg[1].strftime('%d %b')})"))
        # cocokkan order TP/SL dengan lot
        for kol, nama, harga_sistem in (("order_tp", "TP", num(r["tp1"])), ("order_sl", "SL", num(r["stop"]))):
            od = parse_orders(r[kol])
            tot = sum(a for a, _ in od)
            if not od:
                aksi.append(dict(urut=3, akun=r["akun"], aksi=f"PASANG {nama}", kode=r["kode"], lot=lot,
                                 harga=harga_sistem or None, nilai=None, tp="", sl="",
                                 alasan=f"belum ada order {nama} tercatat" +
                                        (" (stop basis close: jual manual kalau close di bawah)" if nama == "SL" else "")))
            elif tot != int(lot):
                aksi.append(dict(urut=2, akun=r["akun"], aksi=f"UBAH {nama}", kode=r["kode"], lot=lot,
                                 harga=harga_sistem or None, nilai=None, tp="", sl="",
                                 alasan=f"lot order {nama} {tot} ≠ dipegang {int(lot)}"))
    else:  # warisan / deviasi: hanya cocokkan lot order yang tercatat
        for kol, nama in (("order_tp", "TP"), ("order_sl", "SL")):
            od = parse_orders(r[kol])
            tot = sum(a for a, _ in od)
            if od and tot != int(lot):
                aksi.append(dict(urut=2, akun=r["akun"], aksi=f"UBAH {nama}", kode=r["kode"], lot=lot, harga=None,
                                 nilai=None, tp="", sl="",
                                 alasan=f"{r['asal']}: lot order {nama} {tot} ≠ dipegang {int(lot)}"))
        stop = num(r["stop"])
        if stop > 0 and px < stop:
            aksi.append(dict(urut=1, akun=r["akun"], aksi="CEK STOP", kode=r["kode"], lot=lot, harga=px,
                             nilai=None, tp="", sl="", alasan=f"{r['asal']}: close {rp(px)} di bawah stop {rp(stop)}"))

# ----------------------------------------------------------------- cek antrian
dana_antri = {"OBERLIN": 0.0, "TEKNIKAL": 0.0}
q_eval = {}
for i, r in q_df.iterrows():
    dana = num(r["harga"]) * num(r["lot"]) * 100 * (1 + FEE_BELI)
    d = get_df(r["kode"])
    res = eval_queue(r, d, stock_last) if d is not None else None
    if (r["akun"], r["kode"]) in selesai_hb:
        res = ("CABUT: posisi saudara sudah selesai", stock_last)
    q_eval[i] = res
    if res and res[0] == "TERISI?":
        aksi.append(dict(urut=2, akun=r["akun"], aksi="CEK TERISI", kode=r["kode"], lot=num(r["lot"]),
                         harga=num(r["harga"]), nilai=None, tp="", sl="",
                         alasan=f"low menyentuh {rp(num(r['harga']))} ({res[1].strftime('%d %b')}). Kalau terisi, "
                                f"pindahkan ke posisi (tombol di tab AKSI)"))
        dana_antri[r["akun"]] += dana       # sampai dikonfirmasi, anggap masih terkunci
    elif res:
        aksi.append(dict(urut=2, akun=r["akun"], aksi="CABUT ANTRIAN", kode=r["kode"], lot=num(r["lot"]),
                         harga=num(r["harga"]), nilai=None, tp="", sl="", alasan=res[0].replace("CABUT: ", "")))
    else:
        dana_antri[r["akun"]] += dana

ekuitas = {a: (kas_ob if a == "OBERLIN" else kas_tk) + mv.get(a, 0.0) + dana_antri.get(a, 0.0) for a in AKUN}
basis_hb = ekuitas["OBERLIN"] + (ekuitas["TEKNIKAL"] if basis_opt.startswith("Ekuitas OBERLIN +") else 0.0)
alok_hb = HB_PORSI * basis_hb
dipegang = set(pos_df["kode"]) | set(q_df["kode"])
eksp_m = float(sum(num(r["lot"]) * 100 * last_close(r["kode"], num(r["avg"]))
                   for _, r in pos_df.iterrows() if r["akun"] == "OBERLIN" and r["asal"] == "harmonic_menengah")
               + sum(num(r["harga"]) * num(r["lot"]) * 100
                     for i, r in q_df.iterrows() if r["asal"] == "harmonic_menengah"
                     and (not q_eval.get(i) or q_eval[i][0] == "TERISI?")))
cap_m = HB_MENENGAH_CAP * ekuitas["OBERLIN"]

# ----------------------------------------------------------------- Compounding: order beli TEKNIKAL
ctdf, amb_lama, amb_baru = ct_table(ct_rows, mm)
ct_orders, ct_info = [], []
kas_tk_sisa = kas_tk
alok_ct = CT_PORSI * modal_masuk
held_tk = set(pos_df.loc[pos_df["akun"] == "TEKNIKAL", "kode"])
if not ctdf.empty:
    llock_map = {m["ticker"]: m["llock"] for m in ct_rows}
    for _, r in ctdf.iterrows():
        if r["Status"] != "BELI":
            continue
        if r["Kode"] in held_tk or r["Kode"] in dipegang:
            ct_info.append((r["Kode"], "sudah dipegang"))
            continue
        harga = float(r["Close"])
        lot = int(max(alok_ct - TARIF_MATERAI, 0) // (harga * 100 * (1 + FEE_BELI)))
        if lot <= 0:
            ct_info.append((r["Kode"], "Total Modal Masuk belum diisi" if modal_masuk <= 0 else "dana tidak cukup 1 lot"))
            continue
        nilai = lot * 100 * harga
        cost = nilai * (1 + FEE_BELI) + (TARIF_MATERAI if nilai > 10e6 else 0)
        if cost > kas_tk_sisa:
            ct_info.append((r["Kode"], f"terlewat (kas): butuh {rp(cost)}, sisa {rp(kas_tk_sisa)}"))
            aksi.append(dict(urut=7, akun="TEKNIKAL", aksi="TERLEWAT (KAS)", kode=r["Kode"], lot=lot, harga=harga,
                             nilai=nilai, tp="", sl="", alasan=f"Compounding conf {r['Buy Conf']:.0f}"))
            continue
        kas_tk_sisa -= cost
        ct_orders.append(dict(kode=r["Kode"], lot=lot, harga=harga, llock=llock_map.get(r["Kode"], 0.0)))
        aksi.append(dict(urut=5, akun="TEKNIKAL", aksi="BELI", kode=r["Kode"], lot=lot, harga=harga, nilai=nilai,
                         tp="exit sinyal", sl=f"CL {rp(llock_map.get(r['Kode'], 0))}",
                         alasan=f"Compounding conf {r['Buy Conf']:.0f}, beli sebelum close"))

# ----------------------------------------------------------------- Harmonic: antrian OBERLIN
hb_orders = []       # antrian yang disarankan
kurang_besar = 0.0   # kekurangan kas untuk sinyal Besar SAH
kas_ob_sisa = kas_ob
butuh_pindah = []    # sinyal Besar yang menunggu pindah kas
lewati_m = []        # sinyal Menengah SAH yang dilewati karena jatah 20% penuh
if not hb_df.empty:
    sig = hb_df[hb_df["Status Order"] == "SAH"].copy()
    sig["_sk"] = (sig["Skala"] != "Besar").astype(int)
    sig = sig.sort_values(["_sk", "Jarak PRZ %"])
    for _, r in sig.iterrows():
        if r["Kode"] in dipegang:
            continue
        asal = "harmonic_besar" if r["Skala"] == "Besar" else "harmonic_menengah"
        legs = ([("gabung", r["Antri Atas"], 2 * alok_hb)] if r["Antri Atas"] == r["Antri Bawah"]
                else [("atas", r["Antri Atas"], alok_hb), ("bawah", r["Antri Bawah"], alok_hb)])
        legs = [(b, h_, dn, lot_hb(dn, h_)) for b, h_, dn in legs]
        if any(x[3] <= 0 for x in legs):
            continue
        butuh = sum(x[3] * x[1] * 100 * (1 + FEE_BELI) for x in legs)
        if asal == "harmonic_menengah" and eksp_m + butuh > cap_m + 1:
            lewati_m.append(r["Kode"])
            continue
        item = dict(kode=r["Kode"], asal=asal, legs=legs, butuh=butuh, tp1=r["TP1"], stop=r["Stop (close)"],
                    harga_c=r["Harga C"], pola=r["Pola"], skala=r["Skala"],
                    harga_now=r["Harga"], top=r["Antri Atas"])
        if butuh <= kas_ob_sisa:
            kas_ob_sisa -= butuh
            if asal == "harmonic_menengah":
                eksp_m += butuh
            hb_orders.append(item)
        elif asal == "harmonic_besar" and mm["mode"] == "PANIK":
            item["kurang"] = butuh - max(kas_ob_sisa, 0.0)
            item["pakai_kas_ob"] = max(kas_ob_sisa, 0.0)
            kas_ob_sisa = 0.0
            butuh_pindah.append(item)
        else:
            aksi.append(dict(urut=7, akun="OBERLIN", aksi="TERLEWAT (KAS)", kode=r["Kode"], lot=None, harga=None,
                             nilai=butuh, tp="", sl="", alasan=f"{r['Skala']} {r['Pola']}, kas OBERLIN kurang"))

if lewati_m:
    aksi.append(dict(urut=7, akun="OBERLIN", aksi="LEWATI", kode=", ".join(lewati_m), lot=None, harga=None,
                     nilai=None, tp="", sl="",
                     alasan=f"{len(lewati_m)} sinyal Menengah SAH: jatah penuh ({rp(eksp_m)} dari batas {rp(cap_m)})"))
# ---- penutupan kekurangan kas OBERLIN saat PANIK, urut prioritas sinyal Besar ----
#  a) kas TEKNIKAL yang sudah settle -> transfer sekarang
#  b) kas TEKNIKAL yang belum settle -> transfer setelah T+2, hanya kalau harga butuh >= 3 hari (ARB) ke PRZ
#  c) saham TEKNIKAL yang hari ini memang disuruh JUAL -> pindah saham ke OBERLIN, jual di OBERLIN
idle_tk = max(kas_tk_sisa, 0.0)
pool_now = min(kas_settle, idle_tk)
pool_later = idle_tk - pool_now
jual_tk = [a for a in aksi if a["akun"] == "TEKNIKAL" and a["aksi"] == "JUAL" and pd.notna(a["harga"])]
pindah_now = pindah_later = 0.0
pindah_saham = []
saran_pindah = 0.0
for item in butuh_pindah:
    k = item["kurang"]
    kurang_besar += k
    hari = min_hari_ke_prz(item["harga_now"], item["top"], arb)
    item["min_hari"] = hari
    a_now = min(k, pool_now)
    sisa = k - a_now
    a_later = 0.0
    if sisa > 1 and hari is not None and hari >= 3:
        a_later = min(sisa, pool_later)
        sisa -= a_later
    saham = []
    while sisa > 1 and jual_tk:
        a = jual_tk.pop(0)
        hasil = a["lot"] * 100 * a["harga"] * (1 - FEE_JUAL)
        saham.append((a, hasil))
        sisa -= hasil
    if sisa <= 1:
        pool_now -= a_now
        pool_later -= a_later
        pindah_now += a_now
        pindah_later += a_later
        for a, hasil in saham:
            pindah_saham.append((a, hasil, item["kode"]))
        cara = []
        if a_now > 0:
            cara.append("pindah kas")
        if a_later > 0:
            cara.append(f"pindah kas setelah settle (sempat: min {hari} hari ke PRZ)")
        if saham:
            cara.append("pindah saham lalu jual di OBERLIN")
        hb_orders.append(dict(item, setelah_pindah=" + ".join(cara)))
    else:
        jual_tk = [a for a, _ in saham] + jual_tk      # tidak jadi dipakai
        aksi.append(dict(urut=7, akun="OBERLIN", aksi="TERLEWAT (KAS)", kode=item["kode"], lot=None, harga=None,
                         nilai=item["butuh"], tp="", sl="",
                         alasan=f"kurang {rp(k)}: kas settle, kas belum settle"
                                + ("" if hari is not None and hari >= 3 else " (tidak sempat, PRZ terlalu dekat)")
                                + " dan saham yang dijual hari ini tidak cukup"))
saran_pindah = pindah_now + pindah_later
if pindah_now > 0:
    aksi.append(dict(urut=4, akun="TEKNIKAL→OBERLIN", aksi="PINDAH KAS", kode="-", lot=None, harga=None,
                     nilai=pindah_now, tp="", sl="",
                     alasan="sekarang, dari kas yang sudah settle (mode PANIK: harmonic Besar didahulukan)"))
if pindah_later > 0:
    aksi.append(dict(urut=4, akun="TEKNIKAL→OBERLIN", aksi="PINDAH KAS T+2", kode="-", lot=None, harga=None,
                     nilai=pindah_later, tp="", sl="",
                     alasan="setelah kas settle; antri harmonic dipasang setelah dana masuk OBERLIN"))
for a, hasil, untuk in pindah_saham:
    aksi.append(dict(urut=0, akun="TEKNIKAL→OBERLIN", aksi="PINDAH SAHAM", kode=a["kode"], lot=a["lot"],
                     harga=None, nilai=None, tp="", sl="",
                     alasan=f"lalu JUAL di OBERLIN (±Rp{rp(hasil)}), dananya untuk antri {untuk}"))
    a["akun"] = "OBERLIN"
    a["alasan"] = a["alasan"] + " · dijual di OBERLIN setelah pindah saham"
for item in hb_orders:
    for bag, harga, dana, lot in item["legs"]:
        aksi.append(dict(urut=6, akun="OBERLIN", aksi="ANTRI BELI", kode=item["kode"], lot=lot, harga=harga,
                         nilai=lot * harga * 100, tp=rp(item["tp1"]), sl=f"{rp(item['stop'])} (close)",
                         alasan=f"{item['skala']} {item['pola']} · PRZ {bag}"
                                + (f" · setelah {item['setelah_pindah']}" if item.get("setelah_pindah") else "")))

aksi_df = pd.DataFrame(aksi)
if not aksi_df.empty:
    aksi_df = aksi_df.sort_values(["urut", "akun", "kode"]).reset_index(drop=True)


def build_state_json():
    p = pos_df.copy()
    for i, e in pos_eval.items():
        p.at[i, "ob_streak"] = float(e["ob"])
        p.at[i, "ob_tgl"] = e["ob_tgl"]
    return json.dumps({
        "versi": 2, "disimpan": now.strftime("%Y-%m-%d %H:%M"),
        "kas": {"OBERLIN": kas_ob, "TEKNIKAL": kas_tk}, "kas_settle_teknikal": kas_settle,
        "modal_masuk_teknikal": modal_masuk,
        "posisi": clean_records(p), "antrian": clean_records(q_df),
    }, indent=2, ensure_ascii=False)


# ----------------------------------------------------------------- RINGKASAN
with tab_ring:
    gb = mm["gate_baru"]
    aturan = {"PANIK": "Harmonic Besar didahulukan, kas TEKNIKAL menganggur boleh dipindah.",
              "NORMAL": "Compounding penuh, harmonic dari kas OBERLIN.",
              "EUFORIA": "Stop beli Compounding baru."}[mm["mode"]]
    st.markdown(cards([
        ("MODE PASAR", mm["mode"], MODE_COL[mm["mode"]], aturan),
        ("IHSG 20 HARI BURSA", f"{mm['ret20']:+.1f}%", MODE_COL[mm["mode"]],
         f"IHSG {rp(mm['close'])} · {mm['dd_peak']:+.1f}% dari puncak 1 th"),
        ("GERBANG BEAR", gb["regime"], COL["red"] if gb["regime"] == "BEAR" else COL["green"],
         (f"dasar {rp(gb['trough'])}, {gb['pct_trough']:+.1f}% · ambang conf {amb_baru}")
         if gb["in_ep"] else "tidak dalam episode bear"),
        ("DASAR PORSI HARMONIC", rp(basis_hb), COL["violet"], f"10% = {rp(alok_hb)} per antrian"),
    ]), unsafe_allow_html=True)
    st.markdown(cards([
        ("EKUITAS OBERLIN", rp(ekuitas["OBERLIN"]), COL["text"],
         f"kas {rp(kas_ob)} · saham {rp(mv['OBERLIN'])} · antri {rp(dana_antri['OBERLIN'])}"),
        ("EKUITAS TEKNIKAL", rp(ekuitas["TEKNIKAL"]), COL["text"],
         f"kas {rp(kas_tk)} · saham {rp(mv['TEKNIKAL'])}"),
        ("MENENGAH (OBERLIN)", f"{(eksp_m / ekuitas['OBERLIN'] * 100) if ekuitas['OBERLIN'] > 0 else 0:.0f}%",
         COL["red"] if eksp_m > cap_m else COL["green"], f"{rp(eksp_m)} dari batas {rp(cap_m)}"),
        ("AKSI HARI INI", len(aksi_df), COL["amber"], "lihat tab AKSI HARI INI"),
    ]), unsafe_allow_html=True)
    if saran_pindah > 0 or pindah_saham:
        bag = []
        if pindah_now > 0:
            bag.append(f"<b>pindah kas Rp {rp(pindah_now)}</b> sekarang (sudah settle)")
        if pindah_later > 0:
            bag.append(f"<b>pindah kas Rp {rp(pindah_later)}</b> setelah settle T+2")
        if pindah_saham:
            bag.append("<b>pindah saham</b> " + ", ".join(f"{a['kode']} {rp(a['lot'])} lot" for a, _, _ in pindah_saham)
                       + " lalu jual di OBERLIN")
        st.markdown(f'<div class="mg-move">⇄ TEKNIKAL → OBERLIN: {"; ".join(bag)}. Kekurangan sinyal Besar '
                    f'{rp(kurang_besar)}. Lakukan manual di Stockbit, lalu perbarui angka kas di tab STATE.</div>',
                    unsafe_allow_html=True)
    if pos_df.empty and q_df.empty and kas_ob == 0 and kas_tk == 0:
        st.markdown('<div class="mg-warn">State masih kosong. Muat file state atau impor portfolio.json '
                    'di tab STATE & JURNAL, lalu isi kas kedua akun.</div>', unsafe_allow_html=True)
    st.markdown("**Posisi dipegang**")
    if pos_df.empty:
        st.caption("Belum ada posisi.")
    else:
        status_map = {}
        for a in aksi:
            if a["aksi"] in ("LEWATI", "TERLEWAT (KAS)", "PINDAH KAS", "PINDAH KAS T+2", "ANTRI BELI", "BELI"):
                continue
            status_map.setdefault(a["kode"], []).append(a["aksi"])
        html = ""
        for i, r in pos_df.iterrows():
            lot, avg = num(r["lot"]), num(r["avg"])
            px = last_close(r["kode"], avg)
            pl = (px / avg - 1) * 100 if avg > 0 else 0.0
            st_ = status_map.get(r["kode"], [])
            if any(x in ("JUAL", "CEK STOP") for x in st_):
                lab, c = "JUAL", COL["red"]
            elif st_:
                lab, c = st_[0], COL["amber"]
            else:
                lab, c = "HOLD", COL["green"]
            if r["asal"] == "deviasi":
                c2 = COL["dim"]
            else:
                c2 = c
            info = []
            if r["asal"] == "compounding":
                e = pos_eval.get(i, {})
                info.append(f'CL <b style="color:{COL["red"]}">{rp(num(r["ll20"]))}</b>')
                info.append(f'K <b>{e.get("k") or 0:.0f}</b> · ob <b>{e.get("ob", 0)}/2</b>')
            elif r["asal"] in ("harmonic_besar", "harmonic_menengah"):
                tp1, stp = num(r["tp1"]), num(r["stop"])
                if tp1 > 0:
                    info.append(f'TP1 <b style="color:{COL["green"]}">{rp(tp1)}</b> ({(tp1 / px - 1) * 100:+.1f}%)')
                if stp > 0:
                    info.append(f'stop <b style="color:{COL["red"]}">{rp(stp)}</b> ({(stp / px - 1) * 100:+.1f}%)')
            else:
                od = parse_orders(r["order_tp"])
                if od:
                    info.append("TP " + ", ".join(f"{a_}@{rp(b_)}" for a_, b_ in od))
                ods = parse_orders(r["order_sl"])
                if ods:
                    info.append("SL " + ", ".join(f"{a_}@{rp(b_)}" for a_, b_ in ods))
            plc = COL["green"] if pl >= 0 else COL["red"]
            html += (f'<div class="mg-act" style="border-left:4px solid {c2}">'
                     f'<div class="t"><span class="k">{r["kode"]}</span>'
                     f'<span class="b" style="color:{c};border-color:{c}">{lab}</span></div>'
                     f'<div class="a">{r["akun"]} · {r["asal"]}</div>'
                     f'<div class="r"><b>{rp(lot)} lot</b> · harga <b>{rp(px)}</b> · avg {f"{avg:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")} · '
                     f'<b style="color:{plc}">{pl:+.1f}%</b></div>'
                     + (f'<div class="r">{" · ".join(info)}</div>' if info else "") + "</div>")
        st.markdown(html, unsafe_allow_html=True)
    with st.expander("Grafik IHSG"):
        st.line_chart(ihsg.tail(250).rename("IHSG"), height=220)

# ----------------------------------------------------------------- AKSI
with tab_aksi:
    if aksi_df.empty:
        st.info("Tidak ada aksi hari ini.")
    else:
        AKSI_COL = {"JUAL": COL["red"], "CEK STOP": COL["red"], "CEK TP1": COL["green"],
                    "CEK TERISI": COL["cyan"], "CABUT ANTRIAN": COL["amber"], "UBAH TP": COL["amber"],
                    "UBAH SL": COL["amber"], "PASANG TP": COL["amber"], "PASANG SL": COL["amber"],
                    "PINDAH KAS": COL["cyan"], "PINDAH KAS T+2": COL["cyan"], "PINDAH SAHAM": COL["cyan"],
                    "BELI": COL["green"], "ANTRI BELI": COL["violet"],
                    "LENGKAPI": COL["dim"], "CEK DATA": COL["dim"], "LEWATI": COL["dim"],
                    "TERLEWAT (KAS)": COL["dim"]}
        html = ""
        for _, a in aksi_df.iterrows():
            c = AKSI_COL.get(a["aksi"], COL["text"])
            baris = []
            if pd.notna(a["lot"]) and pd.notna(a["harga"]):
                baris.append(f"<b>{rp(a['lot'])} lot</b> @ <b>{rp(a['harga'])}</b>")
            elif pd.notna(a["lot"]):
                baris.append(f"<b>{rp(a['lot'])} lot</b>")
            elif pd.notna(a["harga"]):
                baris.append(f"harga <b>{rp(a['harga'])}</b>")
            if pd.notna(a["nilai"]):
                baris.append(f"Rp {rp(a['nilai'])}")
            tpsl = []
            if a["tp"]:
                tpsl.append(f'TP <b style="color:{COL["green"]}">{a["tp"]}</b>')
            if a["sl"]:
                tpsl.append(f'SL <b style="color:{COL["red"]}">{a["sl"]}</b>')
            html += (f'<div class="mg-act" style="border-left:4px solid {c}">'
                     f'<div class="t"><span class="k">{a["kode"]}</span>'
                     f'<span class="b" style="color:{c};border-color:{c}">{a["aksi"]}</span></div>'
                     f'<div class="a">{a["akun"]}</div>'
                     + (f'<div class="r">{" · ".join(baris)}</div>' if baris else "")
                     + (f'<div class="r">{" · ".join(tpsl)}</div>' if tpsl else "")
                     + f'<div class="n">{a["alasan"]}</div></div>')
        st.markdown(html, unsafe_allow_html=True)
        with st.expander("Lihat sebagai tabel"):
            tampil = aksi_df.drop(columns="urut").copy()
            for kol in ("lot", "harga", "nilai"):
                tampil[kol] = [rp(x) if pd.notna(x) else "" for x in tampil[kol]]
            st.dataframe(tampil, hide_index=True, width="stretch",
                         column_config={"nilai": st.column_config.TextColumn(width="medium"),
                                        "alasan": st.column_config.TextColumn(width="large")})
    st.caption("Urutan: jual/cek dulu → ubah order & antrian → pindah kas → beli Compounding → antri harmonic. "
               "Harga antri sudah sesuai fraksi BEI. Harmonic: jual semua di TP1, stop basis close harian.")

    st.markdown("**Catat ke state setelah dieksekusi di Stockbit**")
    tgl_today = now.strftime("%Y-%m-%d")
    opsi_hb = [f"{it['kode']} {bag} {lot} lot @{rp(h_)}" for it in hb_orders for bag, h_, _, lot in it["legs"]]
    pilih_hb = st.multiselect("Antrian harmonic yang sudah dipasang", opsi_hb)
    if st.button("➕ Catat antrian terpasang") and pilih_hb:
        add = []
        for it in hb_orders:
            for bag, h_, _, lot in it["legs"]:
                if f"{it['kode']} {bag} {lot} lot @{rp(h_)}" in pilih_hb:
                    add.append(dict(akun="OBERLIN", kode=it["kode"], asal=it["asal"], bagian=bag, harga=h_, lot=lot,
                                    tanggal_pasang=tgl_today, tp1=it["tp1"], stop=it["stop"],
                                    harga_c=it["harga_c"], catatan=f"{it['skala']} {it['pola']}"))
        ss["pos_base"] = pos_df
        ss["q_base"] = to_frame(clean_records(q_df) + add, Q_COLS, NUM_Q)
        ss["ver"] += 1
        st.rerun()
    opsi_ct = [f"{o['kode']} {o['lot']} lot @{rp(o['harga'])}" for o in ct_orders]
    pilih_ct = st.multiselect("Beli Compounding yang sudah terisi (ubah lot/avg di tabel posisi kalau beda)", opsi_ct)
    if st.button("➕ Catat beli Compounding") and pilih_ct:
        add = [dict(akun="TEKNIKAL", kode=o["kode"], asal="compounding", lot=o["lot"], avg=o["harga"],
                    tanggal_beli=stock_last.strftime("%Y-%m-%d"), ll20=o["llock"], ob_streak=0, ob_tgl="",
                    tp1=None, stop=None, harga_c=None, order_tp="", order_sl="", catatan="")
               for o in ct_orders if f"{o['kode']} {o['lot']} lot @{rp(o['harga'])}" in pilih_ct]
        ss["pos_base"] = to_frame(clean_records(pos_df) + add, POS_COLS, NUM_POS)
        ss["q_base"] = q_df
        ss["ver"] += 1
        st.rerun()
    terisi = {i: r for i, r in q_df.iterrows() if q_eval.get(i) and q_eval[i][0] == "TERISI?"}
    opsi_fill = [f"{r['kode']} {r['bagian']} {int(num(r['lot']))} lot @{rp(num(r['harga']))}" for r in terisi.values()]
    pilih_fill = st.multiselect("Antrian yang sudah terisi → pindah ke posisi", opsi_fill)
    if st.button("➕ Pindahkan ke posisi") and pilih_fill:
        add, drop = [], []
        for i, r in terisi.items():
            if f"{r['kode']} {r['bagian']} {int(num(r['lot']))} lot @{rp(num(r['harga']))}" in pilih_fill:
                drop.append(i)
                add.append(dict(akun=r["akun"], kode=r["kode"], asal=r["asal"], lot=r["lot"], avg=r["harga"],
                                tanggal_beli=q_eval[i][1].strftime("%Y-%m-%d"), ll20=None, ob_streak=0, ob_tgl="",
                                tp1=r["tp1"], stop=r["stop"], harga_c=r["harga_c"], order_tp="", order_sl="",
                                catatan=f"antrian {r['bagian']} terisi"))
        ss["pos_base"] = to_frame(clean_records(pos_df) + add, POS_COLS, NUM_POS)
        ss["q_base"] = q_df.drop(index=drop).reset_index(drop=True)
        ss["ver"] += 1
        st.rerun()

    st.markdown("**Ringkasan jurnal (salin ke excel jurnal)**")
    lines = []
    for _, a in (aksi_df.iterrows() if not aksi_df.empty else []):
        if a["aksi"] in ("BELI", "ANTRI BELI", "JUAL", "PINDAH KAS", "PINDAH KAS T+2", "PINDAH SAHAM"):
            lot_txt = f"{int(a['lot'])} lot" if pd.notna(a["lot"]) else ""
            hg = f"@{rp(a['harga'])}" if pd.notna(a["harga"]) else ""
            nil = f"Rp{rp(a['nilai'])}" if pd.notna(a["nilai"]) else ""
            lines.append(" | ".join(x for x in [tgl_today, a["akun"], a["aksi"], a["kode"], f"{lot_txt} {hg}".strip(),
                                                nil, f"TP {a['tp']}" if a["tp"] else "",
                                                f"SL {a['sl']}" if a["sl"] else "", a["alasan"]] if x))
    for _, r in pos_df[pos_df["asal"] == "deviasi"].iterrows():
        lines.append(f"{tgl_today} | {r['akun']} | DEVIASI (dipegang) | {r['kode']} | {int(num(r['lot']))} lot "
                     f"@{num(r['avg']):,.2f} | dipisahkan dari kinerja sistem")
    st.text_area("Rencana transaksi hari ini", "\n".join(lines) or "-", height=180)

# ----------------------------------------------------------------- STATE: unduh
with tab_state:
    st.download_button("⬇ Unduh state JSON (simpan di akhir sesi)", data=build_state_json(),
                       file_name=f"state_gabungan_{now.strftime('%Y-%m-%d')}.json", mime="application/json")
    if pos_eval:
        st.caption("ob_streak dan ob_tgl posisi Compounding di file unduhan sudah diperbarui sampai candle "
                   f"{stock_last.strftime('%d %b %Y')}.")
        st.dataframe(pd.DataFrame([dict(kode=pos_df.at[i, "kode"], K=e["k"], ob_streak=e["ob"], ob_tgl=e["ob_tgl"],
                                         sinyal=e["trig"][0] if e["trig"] else "HOLD")
                                   for i, e in pos_eval.items()]),
                     hide_index=True, width="stretch",
                     column_config={"K": st.column_config.NumberColumn(format="%.1f")})

# ----------------------------------------------------------------- HARMONIC
with tab_hb:
    if hb_df.empty:
        st.info("Belum ada sinyal harmonic bullish skala Besar/Menengah yang lolos syarat.")
    else:
        vv = hb_df.copy()
        vv["Min hari ke PRZ"] = [min_hari_ke_prz(h_, t_, arb) for h_, t_ in zip(vv["Harga"], vv["Antri Atas"])]
        vv["Dipegang/antri"] = vv["Kode"].isin(dipegang).map({True: "ya", False: ""})
        vv["_sk"] = (vv["Skala"] != "Besar").astype(int)
        vv["_so"] = (vv["Status Order"] != "SAH").astype(int)
        vv = vv.sort_values(["_sk", "_so", "Jarak PRZ %"]).drop(columns=["_sk", "_so"]).reset_index(drop=True)
        st.markdown(cards([
            ("SAH BESAR", int(((vv["Skala"] == "Besar") & (vv["Status Order"] == "SAH")).sum()), COL["cyan"],
             "dibuatkan order"),
            ("SAH MENENGAH", int(((vv["Skala"] == "Menengah") & (vv["Status Order"] == "SAH")).sum()), COL["violet"],
             "kalau jatah 20% masih ada"),
            ("TUA", int((vv["Status Order"] == "TUA").sum()), COL["amber"],
             f"PRZ disentuh > {HB_SENTUH_MAX} hari bursa lalu"),
            ("PRZ LEBAR", int((vv["PRZ lebar"] != "").sum()), COL["red"], f"risiko > {HB_LEBAR_X:g}× potensi"),
        ]), unsafe_allow_html=True)
        vv["_o"] = [0 if (so == "SAH" and dp != "ya") else (1 if dp == "ya" else 2)
                    for so, dp in zip(vv["Status Order"], vv["Dipegang/antri"])]
        vv = vv.sort_values(["_o"], kind="stable").drop(columns="_o").reset_index(drop=True)
        SO_COL = {"SAH": COL["cyan"], "TUA": COL["amber"], "KEDALUWARSA": COL["dim"]}
        for j, r in vv.iterrows():
            held = r["Dipegang/antri"] == "ya"
            lab = "DIPEGANG" if held else r["Status Order"]
            c = COL["green"] if held else SO_COL.get(r["Status Order"], COL["red"])
            sentuh = ("belum disentuh" if pd.isna(r["Sentuh PRZ (hari lalu)"])
                      else f'disentuh {int(r["Sentuh PRZ (hari lalu)"])} hari lalu')
            mh = r["Min hari ke PRZ"]
            mh_txt = "sudah di/bawah PRZ" if mh == 0 else (f"min {mh} hari ke PRZ" if mh is not None else "")
            lebar = f' · <b style="color:{COL["red"]}">PRZ LEBAR</b>' if r["PRZ lebar"] else ""
            st.markdown(
                f'<div class="mg-act" style="border-left:4px solid {c}">'
                f'<div class="t"><span class="k">{r["Kode"]}</span>'
                f'<span class="b" style="color:{c};border-color:{c}">{lab}</span></div>'
                f'<div class="a">{r["Skala"]} · {r["Pola"]} · {r["Status"]}</div>'
                f'<div class="r">Harga <b>{rp(r["Harga"])}</b> · jarak PRZ <b>{r["Jarak PRZ %"]:.1f}%</b> · {mh_txt}</div>'
                f'<div class="r">Antri <b style="color:{COL["violet"]}">{rp(r["Antri Atas"])}</b> / '
                f'<b style="color:{COL["violet"]}">{rp(r["Antri Bawah"])}</b> · TP1 '
                f'<b style="color:{COL["green"]}">{rp(r["TP1"])}</b> · stop '
                f'<b style="color:{COL["red"]}">{rp(r["Stop (close)"])}</b></div>'
                f'<div class="r">Dari antri atas: risiko <b style="color:{COL["red"]}">{r["Risiko dari atas %"]:.0f}%</b>'
                f' · potensi <b style="color:{COL["green"]}">+{r["Potensi TP1 dari atas %"]:.0f}%</b>{lebar}</div>'
                f'<div class="n">PRZ {sentuh} · aktif sejak {r["Aktif sejak"]} · {r["Waktu"]}</div></div>',
                unsafe_allow_html=True)
            ck = f'{r["Kode"]}|{r["Skala"]}|{r["Pola"]}|{r["Tanggal C"]}'
            if go is not None and st.button(f"Grafik {r['Kode']} ›", key=f"g_{ck}", width="stretch"):
                ss["_chart"] = None if ss.get("_chart") == ck else ck
            if ss.get("_chart") == ck:
                dd = hb_frame(data_all.get(r["Kode"]))
                p = find_pattern(dd, r["Skala"], r["Pola"], r["Tanggal C"]) if dd is not None else None
                if p is not None:
                    st.plotly_chart(make_chart(r["Kode"], dd, p, r["Skala"]), width="stretch",
                                    config={"displaylogo": False, "scrollZoom": True}, key=f"ch_{ck}")
                else:
                    st.caption("Pola tidak ditemukan ulang (data berubah). Tekan Tarik ulang data.")
        if go is None:
            st.caption("Grafik butuh paket plotly (tambahkan ke requirements.txt).")
        num0 = st.column_config.NumberColumn(format="%.0f")
        num1 = st.column_config.NumberColumn(format="%.1f")
        with st.expander("Lihat sebagai tabel"):
          st.dataframe(
            vv, hide_index=True, width="stretch", height=min(640, 38 + 35 * max(len(vv), 1)),
            column_order=["Kode", "Skala", "Pola", "Status Order", "Dipegang/antri", "Status", "Kategori",
                          "PRZ lebar", "Harga", "Jarak PRZ %", "Min hari ke PRZ", "Antri Atas", "Antri Bawah",
                          "Stop (close)", "TP1", "Harga C", "Risiko dari atas %", "Potensi TP1 dari atas %",
                          "R:R Rencana", "Sentuh PRZ (hari lalu)", "Aktif sejak", "Umur sinyal (hari)",
                          "Waktu", "Tanggal C", "Umur C", "Value Min 20H (M)"],
            column_config={"Harga": num0, "Antri Atas": num0, "Antri Bawah": num0, "Stop (close)": num0,
                           "TP1": num0, "Harga C": num0, "Jarak PRZ %": num1, "Risiko dari atas %": num1,
                           "Potensi TP1 dari atas %": num1,
                           "R:R Rencana": st.column_config.NumberColumn(format="%.2f"),
                           "Value Min 20H (M)": num1})
        st.caption("SAH = pernah masuk jarak ≤15% sejak C, belum tembus C, umur ≤220 hari, PRZ belum disentuh "
                   f"atau baru disentuh ≤{HB_SENTUH_MAX} hari bursa lalu. TUA = tetap tampil, tanpa order.")
    if hb_gagal:
        st.caption(f"{hb_gagal} perhitungan gagal dan dilewati.")

# ----------------------------------------------------------------- COMPOUNDING
with tab_ct:
    if sesi == "SESI SORE":
        st.markdown('<div class="mg-warn">Sesi sore: candle sudah final, pasar sudah tutup. Sinyal Compounding '
                    'dieksekusi di sesi 15.00–16.15 (beli sebelum close). Daftar ini untuk cek saja.</div>',
                    unsafe_allow_html=True)
    if ctdf.empty:
        st.info("Tidak ada kandidat breakout yang lolos gerbang Compounding.")
    else:
        st.markdown(cards([
            ("LOLOS SCREENER", len(ctdf), COL["text"], "semua gerbang kode asli"),
            ("ORDER BELI", len(ct_orders), COL["green"], f"20% modal = {rp(alok_ct)}"),
            ("DICORET / DITAHAN", int((ctdf["Status"] != "BELI").sum()), COL["red"],
             "red-flag, ARA, ambang BEAR, euforia"),
            ("AMBANG CONF", f"{amb_baru}", COL["amber"], f"versi lama: {amb_lama}"),
        ]), unsafe_allow_html=True)
        for _, r in ctdf.iterrows():
            beli = r["Status"] == "BELI"
            c = COL["green"] if beli else COL["dim"]
            conf = float(r["Buy Conf"])
            cc = COL["green"] if conf >= 75 else (COL["amber"] if conf >= 50 else COL["red"])
            st.markdown(
                f'<div class="mg-act" style="border-left:4px solid {c}">'
                f'<div class="t"><span class="k">{r["Kode"]}</span>'
                f'<span class="b" style="color:{c};border-color:{c}">{"BELI" if beli else "DICORET"}</span></div>'
                f'<div class="r">Conf <b style="color:{cc}">{conf:.0f}%</b> · close <b>{rp(r["Close"])}</b> '
                f'({r["Naik hari ini %"]:+.1f}%) · CL <b style="color:{COL["red"]}">{rp(r["CL (LL20)"])}</b></div>'
                f'<div class="mg-bar"><div style="width:{conf:.0f}%;background:{cc}"></div></div>'
                f'<div class="n">K {r["K"]:.0f} · fase {r["Fase"]} · vol ratio {r["Vol Ratio"]:.2f}'
                + ("" if beli else f' · {r["Status"]}') + '</div></div>', unsafe_allow_html=True)
        with st.expander("Lihat sebagai tabel"):
          st.dataframe(ctdf, hide_index=True, width="stretch", height=min(640, 38 + 35 * max(len(ctdf), 1)),
                     column_config={"Buy Conf": st.column_config.NumberColumn(format="%.0f"),
                                    "Close": st.column_config.NumberColumn(format="%.0f"),
                                    "CL (LL20)": st.column_config.NumberColumn(format="%.0f"),
                                    "HH20": st.column_config.NumberColumn(format="%.0f"),
                                    "Naik hari ini %": st.column_config.NumberColumn(format="%.1f"),
                                    "K": st.column_config.NumberColumn(format="%.1f"),
                                    "Vol Ratio": st.column_config.NumberColumn(format="%.2f"),
                                    "Value MA20 (M)": st.column_config.NumberColumn(format="%.1f")})
        for kode, why in ct_info:
            st.caption(f"{kode}: {why}")

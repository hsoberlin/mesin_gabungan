# -*- coding: utf-8 -*-
"""
MESIN GABUNGAN — Tahap 1 (mesin inti)
Compounding Terminal + Harmonic Board (skala Besar & Menengah) dalam satu pemindai.

Isi tahap 1:
  1. Mode pasar dari IHSG 20 hari bursa (PANIK / NORMAL / EUFORIA)
     + gerbang BEAR Compounding versi lama dan versi perbaikan (tutup lagi saat dasar baru).
  2. Scan Harmonic (bullish, Besar + Menengah) memakai detect_patterns asli Harmonic Board,
     ditambah: sentuh PRZ N hari lalu, flag PRZ lebar, status "pernah <=15% sejak C",
     minimal hari ke PRZ dengan batas ARB.
  3. Scan Compounding memakai logika analyze_stock asli, ditambah filter ARA,
     red-flag, ambang BEAR versi perbaikan, dan rem euforia.
  4. Tab uji kecocokan dengan aplikasi lama.
Belum ada: alokasi kas, daftar order, state JSON (tahap 2).

Jalankan : streamlit run mesin_gabungan.py
Butuh    : streamlit>=1.50, yfinance, pandas, numpy
Data     : Yahoo Finance. Candle harian baru representatif setelah ±16.15 WIB.
"""
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


@st.cache_data(ttl=6 * 3600, show_spinner=False)
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


@st.cache_data(ttl=6 * 3600, show_spinner=False)
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


@st.cache_data(ttl=6 * 3600, show_spinner=False)
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
                rows.append({
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
    return dict(close=float(close_now), ll20=float(ll20), hh20=float(hh20), stoch_k=float(stoch_k_now),
                vol_ratio=float(vol_ratio), fase=int(fase), buy_confidence=float(buy_conf),
                val_ma20=float(val_ma20) / 1e9, kunci_ara=bool(kunci_ara),
                chg=(float(close_now) / prev_close - 1) * 100)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
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
# 8. ANTARMUKA
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
  <div class="mg-sub">TAHAP 1 // MODE PASAR · HARMONIC BESAR+MENENGAH · COMPOUNDING</div>
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


with st.sidebar:
    st.markdown("### ▌PARAMETER")
    arb = st.number_input("Batas ARB harian (%)", 1.0, 35.0, ARB_DEFAULT, 0.5,
                          help="ARB asimetris 7% berlaku 19 Okt s.d. 31 Des 2026. "
                               "Dipakai untuk menghitung minimal berapa hari harga bisa sampai PRZ.")
    if st.button("▶ TARIK ULANG DATA", width="stretch"):
        load_all.clear()
        load_ihsg.clear()
        scan_harmonic.clear()
        scan_compounding.clear()
        st.rerun()
    st.caption(f"Universe gabungan {len(ALL_TICKERS)} kode "
               f"(Harmonic {len(HB_TICKERS)}, Compounding {len(CT_TICKERS)}). Data Yahoo 2 tahun, "
               "cache 6 jam.")

now = datetime.now(WIB)
with st.spinner("Menarik data IHSG..."):
    ihsg = load_ihsg()
if ihsg is None or len(ihsg) < 260:
    st.error("Data IHSG (^JKSE) gagal ditarik. Coba tarik ulang beberapa menit lagi.")
    st.stop()
mm = market_mode(ihsg)

with st.spinner(f"Menarik data {len(ALL_TICKERS)} emiten & memindai... (pertama kali bisa 2-4 menit)"):
    hb_df, hb_gagal = scan_harmonic(ALL_TICKERS)
    ct_rows = scan_compounding(ALL_TICKERS)
    n_loaded = len(load_all(ALL_TICKERS))

tgl_data = mm["tanggal"]
if tgl_data.date() == now.date() and (now.hour, now.minute) < (16, 15):
    st.markdown('<div class="mg-warn"><b>Candle hari ini belum final.</b> Data Yahoo baru representatif '
                'setelah ±16.15 WIB. Jangan ambil keputusan dari angka ini; buka lagi sore dan tekan '
                '"Tarik ulang data".</div>', unsafe_allow_html=True)
st.caption(f"Data per {tgl_data.strftime('%d %b %Y')} · dibuka {now.strftime('%d %b %Y %H:%M')} WIB · "
           f"{n_loaded} emiten termuat")

tab_mode, tab_hb, tab_ct, tab_uji = st.tabs(["▌MODE PASAR", "▌HARMONIC", "▌COMPOUNDING", "▌UJI KECOCOKAN"])

# ----------------------------------------------------------------- MODE PASAR
with tab_mode:
    gl, gb = mm["gate_lama"], mm["gate_baru"]
    aturan = {"PANIK": "Harmonic Besar didahulukan memakai cash, sisanya Compounding.",
              "NORMAL": "Compounding penuh, Harmonic Besar dari sisa kas.",
              "EUFORIA": "Stop beli Compounding baru."}[mm["mode"]]
    st.markdown(cards([
        ("MODE PASAR", mm["mode"], MODE_COL[mm["mode"]], aturan),
        ("IHSG 20 HARI BURSA", f"{mm['ret20']:+.1f}%", MODE_COL[mm["mode"]],
         f"PANIK ≤ {PANIK_RET20*100:.0f}% · EUFORIA > +{EUFORIA_RET20*100:.0f}%"),
        ("IHSG", rp(mm["close"]), COL["text"], f"{mm['dd_peak']:+.1f}% dari puncak 1 tahun"),
        ("GERBANG BEAR (PERBAIKAN)", gb["regime"], COL["red"] if gb["regime"] == "BEAR" else COL["green"],
         (f"dasar {rp(gb['trough'])} ({gb['trough_date'].strftime('%d %b %y')}), "
          f"{gb['pct_trough']:+.1f}% dari dasar · butuh +20%") if gb["in_ep"] else "tidak dalam episode bear"),
    ]), unsafe_allow_html=True)
    if gl["regime"] != gb["regime"]:
        st.markdown(f'<div class="mg-warn">Gerbang versi lama (Compounding Terminal) masih <b>{gl["regime"]}</b>, '
                    f'versi perbaikan <b>{gb["regime"]}</b>. Selisihnya: saat BEAR, kandidat Compounding '
                    f'hanya diambil kalau Buy Confidence ≥ {AMBANG_CONF_BEAR}.</div>', unsafe_allow_html=True)
    ser = ihsg.tail(250).rename("IHSG")
    st.line_chart(ser, height=260)
    r20 = (ihsg / ihsg.shift(20) - 1).tail(250) * 100
    st.caption("Perubahan IHSG 20 hari bursa (%). Garis di bawah -5 = PANIK, di atas +10 = EUFORIA.")
    st.line_chart(pd.DataFrame({"IHSG 20H %": r20, "Batas PANIK": -5.0, "Batas EUFORIA": 10.0}), height=200)

# ----------------------------------------------------------------- HARMONIC
with tab_hb:
    if hb_df.empty:
        st.info("Belum ada sinyal harmonic bullish skala Besar/Menengah yang lolos syarat.")
    else:
        v = hb_df.copy()
        v["Min hari ke PRZ"] = [min_hari_ke_prz(h_, t_, arb) for h_, t_ in zip(v["Harga"], v["Antri Atas"])]
        v["_sk"] = (v["Skala"] != "Besar").astype(int)
        v["_kt"] = (v["Kategori"] != "SINYAL").astype(int)
        v = v.sort_values(["_sk", "_kt", "Jarak PRZ %"]).drop(columns=["_sk", "_kt"]).reset_index(drop=True)
        nb = int(((v["Skala"] == "Besar") & (v["Kategori"] == "SINYAL")).sum())
        nm = int(((v["Skala"] == "Menengah") & (v["Kategori"] == "SINYAL")).sum())
        npr = int((v["Kategori"] != "SINYAL").sum())
        nlb = int((v["PRZ lebar"] != "").sum())
        st.markdown(cards([
            ("SINYAL BESAR", nb, COL["cyan"], "jarak ≤15% hari ini"),
            ("SINYAL MENENGAH", nm, COL["violet"], "maks 20% porto (diatur di tahap 2)"),
            ("PERNAH ≤15%", npr, COL["amber"], "sempat aktif sejak C, kini menjauh"),
            ("PRZ LEBAR", nlb, COL["red"], f"risiko dari antri atas > {HB_LEBAR_X:g}× potensi"),
        ]), unsafe_allow_html=True)
        pilih = st.multiselect("Skala", ["Besar", "Menengah"], default=["Besar", "Menengah"])
        v = v[v["Skala"].isin(pilih)]
        num0 = st.column_config.NumberColumn(format="%.0f")
        num1 = st.column_config.NumberColumn(format="%.1f")
        num2 = st.column_config.NumberColumn(format="%.2f")
        st.dataframe(
            v, hide_index=True, width="stretch", height=min(640, 38 + 35 * max(len(v), 1)),
            column_order=["Kode", "Skala", "Pola", "Status", "Kategori", "PRZ lebar", "Harga",
                          "Jarak PRZ %", "Min hari ke PRZ", "Antri Atas", "Antri Bawah", "Stop (close)",
                          "TP1", "Risiko dari atas %", "Potensi TP1 dari atas %", "R:R Rencana",
                          "Sentuh PRZ (hari lalu)", "Aktif sejak", "Hari aktif", "Waktu", "Tanggal C",
                          "Umur C", "TP2", "Value Min 20H (M)"],
            column_config={"Harga": num0, "Antri Atas": num0, "Antri Bawah": num0, "Stop (close)": num0,
                           "TP1": num0, "TP2": num0, "Jarak PRZ %": num1, "Risiko dari atas %": num1,
                           "Potensi TP1 dari atas %": num1, "R:R Rencana": num2,
                           "Value Min 20H (M)": num1},
        )
        st.caption("Semua pola bullish. Harga antri sudah sesuai fraksi BEI. Stop dihitung dari close harian. "
                   "Aturan keluar: jual semua di TP1. 'Sentuh PRZ' = berapa hari lalu low pertama kali masuk PRZ; "
                   "makin besar angkanya, pola makin tua. 'PRZ lebar' = kalau antri di batas atas, risiko ke stop "
                   "lebih dari 2× potensi ke TP1 (kasus DSSA): sebaiknya hanya antri di batas bawah atau dilewati.")
    if hb_gagal:
        st.caption(f"{hb_gagal} perhitungan gagal dan dilewati.")

# ----------------------------------------------------------------- COMPOUNDING
with tab_ct:
    ctdf, amb_lama, amb_baru = ct_table(ct_rows, mm)
    if ctdf.empty:
        st.info("Tidak ada kandidat breakout yang lolos gerbang Compounding hari ini.")
    else:
        nbeli = int((ctdf["Status"] == "BELI").sum())
        st.markdown(cards([
            ("LOLOS SCREENER", len(ctdf), COL["text"], "semua gerbang kode asli"),
            ("SIAP BELI", nbeli, COL["green"], "urut Buy Confidence"),
            ("DICORET / DITAHAN", len(ctdf) - nbeli, COL["red"], "red-flag, ARA, ambang BEAR, euforia"),
            ("AMBANG CONF", f"{amb_baru}", COL["amber"], f"versi lama: {amb_lama}"),
        ]), unsafe_allow_html=True)
        num0 = st.column_config.NumberColumn(format="%.0f")
        num1 = st.column_config.NumberColumn(format="%.1f")
        num2 = st.column_config.NumberColumn(format="%.2f")
        st.dataframe(ctdf, hide_index=True, width="stretch",
                     height=min(640, 38 + 35 * max(len(ctdf), 1)),
                     column_config={"Buy Conf": num0, "Close": num0, "CL (LL20)": num0, "HH20": num0,
                                    "Naik hari ini %": num1, "K": num1, "Vol Ratio": num2,
                                    "Value MA20 (M)": num1})
        st.caption("Beli di close hari breakout, porsi 20% modal per posisi (sizing di tahap 2). "
                   "Exit: close < CL (LL20 dikunci saat beli), atau K>80 dua hari beruntun, atau K>80 sehari "
                   "dan low ≤ harga beli (tidak berlaku di hari beli). Saham yang sudah dipegang belum dicoret "
                   "di tahap ini.")

# ----------------------------------------------------------------- UJI KECOCOKAN
with tab_uji:
    st.markdown("**Cara uji (sore, setelah 16.15 WIB, di hari yang sama):**")
    st.markdown(
        "1. **Harmonic Board lama**, setelan: skala *Besar (5×ATR)*, umur C 150, basis stop *Close harian*, "
        "buffer 0, arah *Bullish*, status *Di PRZ + Menuju PRZ*, posisi semua, tembus 50, "
        "**R:R minimum 0,5**, jarak maks 15%, value 1. Ulangi untuk skala *Menengah (3×ATR)*, umur C 80.\n"
        "2. **Compounding Terminal lama**: tekan *Pindai Pasar*.\n"
        "3. Bandingkan dengan daftar di bawah. Selisih yang **disengaja**: kategori *PERNAH ≤15%* "
        "(tidak ada di app lama), red-flag dan ARA (app lama tetap menampilkan), ambang BEAR versi perbaikan, "
        "dan saham yang sudah dipegang (app lama menyembunyikannya).")
    if not hb_df.empty:
        for sk in ("Besar", "Menengah"):
            x = hb_df[(hb_df["Skala"] == sk) & (hb_df["Kategori"] == "SINYAL")]
            kode = ", ".join(sorted(f"{a} ({b})" for a, b in zip(x["Kode"], x["Pola"]))) or "-"
            st.markdown(f"**Harmonic {sk}: {len(x)} pola** → {kode}")
    else:
        st.markdown("**Harmonic:** tidak ada sinyal.")
    if ct_rows:
        ctdf, amb_lama, _ = ct_table(ct_rows, mm)
        lama = ctdf[ctdf["Tampil di app lama"] == "Ya"]
        st.markdown(f"**Compounding (versi app lama, ambang {amb_lama}): {len(lama)} kandidat** → "
                    + (", ".join(lama.sort_values("Buy Conf", ascending=False)
                                 .apply(lambda r: f"{r['Kode']} {r['Buy Conf']:.0f}%", axis=1)) or "-"))
    else:
        st.markdown("**Compounding:** tidak ada kandidat.")
    st.caption("Catatan teknis: data Harmonic dibentuk persis seperti app lama (buang baris volume nol, "
               "riwayat 2 tahun). Compounding memakai data yang sama tanpa membuang baris volume nol, "
               "seperti app lama. Kalau ada selisih di luar daftar 'disengaja', kirim screenshot kedua app.")

-- ============================================
-- BALI RENOVATION OS - MATERIALS SEED DATA
-- Migration: 001_materials_seed.sql
-- Target: 150+ construction materials for Bali
-- ============================================

-- Clear existing test data (safe for dev)
-- DELETE FROM materials WHERE material_code LIKE 'MAT%';

-- ============================================
-- CEMENT & CONCRETE (MAT001-MAT020)
-- ============================================

INSERT INTO materials (material_code, name_id, name_en, category, subcategory, unit, aliases, tokopedia_search, price_avg) VALUES
('MAT001', 'Semen Portland 50kg', 'Portland Cement 50kg', 'cement_concrete', 'cement', 'sak', ARRAY['semen', 'cement', 'PC', 'semen abu'], 'semen portland 50kg tiga roda', 65000),
('MAT002', 'Semen Putih 40kg', 'White Cement 40kg', 'cement_concrete', 'cement', 'sak', ARRAY['semen putih', 'white cement'], 'semen putih 40kg', 95000),
('MAT003', 'Pasir Cor', 'Construction Sand', 'cement_concrete', 'aggregate', 'pickup', ARRAY['pasir', 'sand', 'pasir bangunan'], 'pasir cor bangunan bali', 350000),
('MAT004', 'Pasir Pasang', 'Plastering Sand', 'cement_concrete', 'aggregate', 'pickup', ARRAY['pasir halus', 'fine sand'], 'pasir pasang halus', 400000),
('MAT005', 'Batu Split 1-2', 'Crushed Stone 1-2cm', 'cement_concrete', 'aggregate', 'pickup', ARRAY['split', 'kerikil', 'gravel', 'batu pecah'], 'batu split 1-2 cor', 450000),
('MAT006', 'Batu Split 2-3', 'Crushed Stone 2-3cm', 'cement_concrete', 'aggregate', 'pickup', ARRAY['split besar', 'coarse gravel'], 'batu split 2-3', 420000),
('MAT007', 'Beton Ready Mix K-225', 'Ready Mix Concrete K-225', 'cement_concrete', 'ready_mix', 'm³', ARRAY['beton cor', 'ready mix', 'beton jadi'], 'ready mix k225 bali', 950000),
('MAT008', 'Beton Ready Mix K-300', 'Ready Mix Concrete K-300', 'cement_concrete', 'ready_mix', 'm³', ARRAY['beton cor', 'ready mix k300'], 'ready mix k300 bali', 1050000),
('MAT009', 'Beton Ready Mix K-350', 'Ready Mix Concrete K-350', 'cement_concrete', 'ready_mix', 'm³', ARRAY['beton cor', 'ready mix k350'], 'ready mix k350 bali', 1150000),
('MAT010', 'Semen Instan', 'Instant Cement', 'cement_concrete', 'cement', 'sak', ARRAY['mortar', 'semen siap pakai'], 'semen instan mortar', 55000),

-- ============================================
-- STRUCTURAL (MAT021-MAT045)
-- ============================================

('MAT021', 'Besi Beton 6mm', 'Rebar 6mm', 'structural', 'rebar', 'batang', ARRAY['besi', 'rebar', 'tulangan', 'begel'], 'besi beton 6mm polos', 25000),
('MAT022', 'Besi Beton 8mm', 'Rebar 8mm', 'structural', 'rebar', 'batang', ARRAY['besi 8', 'rebar 8mm'], 'besi beton 8mm polos', 35000),
('MAT023', 'Besi Beton 10mm', 'Rebar 10mm', 'structural', 'rebar', 'batang', ARRAY['besi 10', 'rebar 10mm', 'tulangan'], 'besi beton 10mm ulir', 55000),
('MAT024', 'Besi Beton 12mm', 'Rebar 12mm', 'structural', 'rebar', 'batang', ARRAY['besi 12', 'rebar 12mm'], 'besi beton 12mm ulir', 75000),
('MAT025', 'Besi Beton 16mm', 'Rebar 16mm', 'structural', 'rebar', 'batang', ARRAY['besi 16', 'rebar 16mm'], 'besi beton 16mm ulir', 130000),
('MAT026', 'Bata Merah', 'Red Brick', 'structural', 'masonry', 'buah', ARRAY['batu bata', 'brick', 'bata press'], 'bata merah press bali', 800),
('MAT027', 'Batako', 'Concrete Block', 'structural', 'masonry', 'buah', ARRAY['batako press', 'block'], 'batako press tebal', 3500),
('MAT028', 'Bata Ringan Hebel', 'AAC Block Hebel', 'structural', 'masonry', 'buah', ARRAY['hebel', 'AAC', 'bata ringan', 'celcon'], 'bata ringan hebel 10cm', 12000),
('MAT029', 'Roster Beton', 'Concrete Ventilation Block', 'structural', 'masonry', 'buah', ARRAY['roster', 'ventilasi', 'lubang angin'], 'roster beton minimalis', 15000),
('MAT030', 'Kawat Bendrat', 'Binding Wire', 'structural', 'accessories', 'kg', ARRAY['kawat ikat', 'tie wire', 'bendrat'], 'kawat bendrat 1kg', 22000),
('MAT031', 'Wiremesh M6', 'Welded Wire Mesh M6', 'structural', 'mesh', 'lembar', ARRAY['wiremesh', 'mesh besi'], 'wiremesh m6 2.1x5.4', 180000),
('MAT032', 'Wiremesh M8', 'Welded Wire Mesh M8', 'structural', 'mesh', 'lembar', ARRAY['wiremesh m8', 'mesh besi'], 'wiremesh m8 2.1x5.4', 280000),
('MAT033', 'Hollow Galvanis 40x40', 'Galvanized Hollow 40x40', 'structural', 'steel', 'batang', ARRAY['hollow', 'besi hollow'], 'hollow galvanis 40x40', 95000),
('MAT034', 'Hollow Galvanis 40x80', 'Galvanized Hollow 40x80', 'structural', 'steel', 'batang', ARRAY['hollow', 'besi hollow'], 'hollow galvanis 40x80', 145000),
('MAT035', 'Besi WF 150', 'Wide Flange Steel 150', 'structural', 'steel', 'batang', ARRAY['WF', 'wide flange', 'H beam'], 'besi WF 150 6m', 1800000),

-- ============================================
-- TILES & FLOORING (MAT046-MAT070)
-- ============================================

('MAT046', 'Keramik 30x30 Putih', 'Ceramic Tile 30x30 White', 'tiles', 'ceramic', 'm²', ARRAY['keramik', 'ceramic', 'tile', 'lantai'], 'keramik 30x30 putih polos', 45000),
('MAT047', 'Keramik 40x40 Motif', 'Ceramic Tile 40x40 Patterned', 'tiles', 'ceramic', 'm²', ARRAY['keramik 40', 'ceramic tile'], 'keramik 40x40 motif', 55000),
('MAT048', 'Keramik 60x60 Glossy', 'Ceramic Tile 60x60 Glossy', 'tiles', 'ceramic', 'm²', ARRAY['keramik 60', 'ceramic 60x60'], 'keramik 60x60 glossy', 85000),
('MAT049', 'Granit 60x60', 'Granite Tile 60x60', 'tiles', 'granite', 'm²', ARRAY['granit', 'granite', 'granito'], 'granit tile 60x60', 150000),
('MAT050', 'Granit 80x80', 'Granite Tile 80x80', 'tiles', 'granite', 'm²', ARRAY['granit 80', 'granite large'], 'granit 80x80 glossy', 220000),
('MAT051', 'Marmer Lokal', 'Local Marble', 'tiles', 'marble', 'm²', ARRAY['marmer', 'marble', 'batu marmer'], 'marmer lokal tulungagung', 350000),
('MAT052', 'Marmer Import', 'Imported Marble', 'tiles', 'marble', 'm²', ARRAY['marmer import', 'carrara'], 'marmer import italy', 850000),
('MAT053', 'Keramik Dinding 25x40', 'Wall Tile 25x40', 'tiles', 'wall_tile', 'm²', ARRAY['keramik dinding', 'wall tile'], 'keramik dinding 25x40', 55000),
('MAT054', 'Mozaik Keramik', 'Ceramic Mosaic', 'tiles', 'mosaic', 'm²', ARRAY['mozaik', 'mosaic', 'mosaik'], 'mozaik keramik kolam', 180000),
('MAT055', 'Batu Alam Andesit', 'Andesite Natural Stone', 'tiles', 'natural_stone', 'm²', ARRAY['batu alam', 'andesit', 'natural stone'], 'batu alam andesit', 120000),
('MAT056', 'Batu Palimanan', 'Palimanan Stone', 'tiles', 'natural_stone', 'm²', ARRAY['palimanan', 'batu paras'], 'batu palimanan cream', 180000),
('MAT057', 'Batu Candi', 'Temple Stone', 'tiles', 'natural_stone', 'm²', ARRAY['batu candi', 'paras jogja'], 'batu candi hitam', 250000),
('MAT058', 'Vinyl Flooring', 'Vinyl Flooring', 'tiles', 'vinyl', 'm²', ARRAY['vinyl', 'lantai vinyl'], 'vinyl flooring motif kayu', 85000),
('MAT059', 'SPC Flooring', 'SPC Flooring', 'tiles', 'vinyl', 'm²', ARRAY['SPC', 'stone plastic composite'], 'SPC flooring 4mm', 150000),
('MAT060', 'Keramik Anti Slip', 'Anti-Slip Ceramic', 'tiles', 'ceramic', 'm²', ARRAY['anti slip', 'kamar mandi', 'bathroom tile'], 'keramik anti slip kamar mandi', 75000),

-- ============================================
-- WOOD & TIMBER (MAT071-MAT090)
-- ============================================

('MAT071', 'Kayu Jati Balok 6x12', 'Teak Beam 6x12cm', 'wood', 'structural', 'batang', ARRAY['kayu jati', 'teak', 'jati', 'balok'], 'kayu jati balok 6x12 4m', 450000),
('MAT072', 'Kayu Jati Papan 2x20', 'Teak Board 2x20cm', 'wood', 'board', 'batang', ARRAY['papan jati', 'teak board'], 'kayu jati papan 2x20', 180000),
('MAT073', 'Kayu Bengkirai Balok', 'Bengkirai Beam', 'wood', 'structural', 'batang', ARRAY['bengkirai', 'yellow balau'], 'kayu bengkirai balok', 380000),
('MAT074', 'Kayu Merbau Decking', 'Merbau Decking', 'wood', 'decking', 'm²', ARRAY['merbau', 'decking', 'outdoor'], 'decking kayu merbau', 650000),
('MAT075', 'Kayu Ulin Decking', 'Ironwood Decking', 'wood', 'decking', 'm²', ARRAY['ulin', 'ironwood', 'kayu besi'], 'decking kayu ulin', 850000),
('MAT076', 'Plywood 9mm', 'Plywood 9mm', 'wood', 'panel', 'lembar', ARRAY['plywood', 'triplek', 'multiplek'], 'plywood 9mm 122x244', 125000),
('MAT077', 'Plywood 18mm', 'Plywood 18mm', 'wood', 'panel', 'lembar', ARRAY['plywood 18', 'multiplek tebal'], 'plywood 18mm 122x244', 250000),
('MAT078', 'MDF 18mm', 'MDF 18mm', 'wood', 'panel', 'lembar', ARRAY['MDF', 'medium density'], 'MDF 18mm 122x244', 180000),
('MAT079', 'Blockboard 18mm', 'Blockboard 18mm', 'wood', 'panel', 'lembar', ARRAY['blockboard', 'papan blok'], 'blockboard 18mm teak', 280000),
('MAT080', 'Kayu Kamper Balok', 'Camphor Beam', 'wood', 'structural', 'batang', ARRAY['kamper', 'camphor wood'], 'kayu kamper balok 6x12', 280000),
('MAT081', 'WPC Decking', 'WPC Decking', 'wood', 'composite', 'm²', ARRAY['WPC', 'wood plastic composite'], 'WPC decking outdoor', 350000),
('MAT082', 'Lisplang GRC', 'GRC Fascia Board', 'wood', 'composite', 'm', ARRAY['lisplang', 'fascia', 'GRC board'], 'lisplang GRC motif kayu', 85000),

-- ============================================
-- ELECTRICAL (MAT091-MAT110)
-- ============================================

('MAT091', 'Kabel NYM 3x2.5mm', 'NYM Cable 3x2.5mm', 'electrical', 'cable', 'meter', ARRAY['kabel', 'cable', 'NYM', 'listrik'], 'kabel NYM 3x2.5mm supreme', 18000),
('MAT092', 'Kabel NYM 3x1.5mm', 'NYM Cable 3x1.5mm', 'electrical', 'cable', 'meter', ARRAY['kabel NYM', 'cable'], 'kabel NYM 3x1.5mm', 12000),
('MAT093', 'Kabel NYY 4x10mm', 'NYY Cable 4x10mm', 'electrical', 'cable', 'meter', ARRAY['kabel NYY', 'underground cable'], 'kabel NYY 4x10mm', 85000),
('MAT094', 'Conduit PVC 20mm', 'PVC Conduit 20mm', 'electrical', 'conduit', 'batang', ARRAY['conduit', 'pipa listrik'], 'conduit PVC 20mm 4m', 25000),
('MAT095', 'Conduit PVC 25mm', 'PVC Conduit 25mm', 'electrical', 'conduit', 'batang', ARRAY['conduit 25', 'pipa listrik'], 'conduit PVC 25mm 4m', 35000),
('MAT096', 'Stop Kontak', 'Power Outlet', 'electrical', 'fitting', 'buah', ARRAY['stop kontak', 'outlet', 'colokan'], 'stop kontak panasonic', 35000),
('MAT097', 'Saklar Tunggal', 'Single Switch', 'electrical', 'fitting', 'buah', ARRAY['saklar', 'switch'], 'saklar tunggal panasonic', 28000),
('MAT098', 'Saklar Ganda', 'Double Switch', 'electrical', 'fitting', 'buah', ARRAY['saklar ganda', 'double switch'], 'saklar ganda panasonic', 45000),
('MAT099', 'MCB 1P 16A', 'MCB 1 Pole 16A', 'electrical', 'breaker', 'buah', ARRAY['MCB', 'breaker', 'pemutus'], 'MCB schneider 1P 16A', 65000),
('MAT100', 'MCB Box 4 Way', 'MCB Box 4 Way', 'electrical', 'panel', 'buah', ARRAY['MCB box', 'panel box'], 'MCB box 4 way surface', 85000),
('MAT101', 'Lampu LED 12W', 'LED Bulb 12W', 'electrical', 'lighting', 'buah', ARRAY['lampu', 'LED', 'bohlam'], 'lampu LED philips 12W', 45000),
('MAT102', 'Downlight LED 9W', 'LED Downlight 9W', 'electrical', 'lighting', 'buah', ARRAY['downlight', 'lampu tanam'], 'downlight LED 9W 4 inch', 75000),
('MAT103', 'Lampu Taman', 'Garden Light', 'electrical', 'lighting', 'buah', ARRAY['lampu taman', 'garden lamp', 'outdoor'], 'lampu taman minimalis', 150000),
('MAT104', 'Kabel Grounding 16mm', 'Grounding Cable 16mm', 'electrical', 'cable', 'meter', ARRAY['grounding', 'arde', 'earth'], 'kabel grounding BC 16mm', 45000),
('MAT105', 'Panel Box', 'Electrical Panel Box', 'electrical', 'panel', 'buah', ARRAY['panel', 'box panel', 'distribution'], 'panel box 60x40', 450000),

-- ============================================
-- PLUMBING (MAT111-MAT135)
-- ============================================

('MAT111', 'Pipa PVC 1/2"', 'PVC Pipe 1/2"', 'plumbing', 'pipe', 'batang', ARRAY['pipa', 'pipe', 'PVC'], 'pipa PVC rucika 1/2 inch 4m', 18000),
('MAT112', 'Pipa PVC 3/4"', 'PVC Pipe 3/4"', 'plumbing', 'pipe', 'batang', ARRAY['pipa PVC 3/4'], 'pipa PVC 3/4 inch 4m', 25000),
('MAT113', 'Pipa PVC 1"', 'PVC Pipe 1"', 'plumbing', 'pipe', 'batang', ARRAY['pipa PVC 1 inch'], 'pipa PVC 1 inch 4m', 35000),
('MAT114', 'Pipa PVC 4"', 'PVC Pipe 4"', 'plumbing', 'drain', 'batang', ARRAY['pipa 4 inch', 'drain pipe'], 'pipa PVC 4 inch 4m', 75000),
('MAT115', 'Pipa PPR 1/2"', 'PPR Pipe 1/2"', 'plumbing', 'pipe', 'batang', ARRAY['PPR', 'pipa panas'], 'pipa PPR 1/2 inch 4m', 35000),
('MAT116', 'Pipa PPR 3/4"', 'PPR Pipe 3/4"', 'plumbing', 'pipe', 'batang', ARRAY['PPR 3/4'], 'pipa PPR 3/4 inch 4m', 55000),
('MAT117', 'Kran Air', 'Water Faucet', 'plumbing', 'fitting', 'buah', ARRAY['kran', 'keran', 'faucet'], 'kran air kuningan', 45000),
('MAT118', 'Kran Shower', 'Shower Mixer', 'plumbing', 'fitting', 'buah', ARRAY['shower mixer', 'kran shower'], 'kran shower mixer', 350000),
('MAT119', 'Floor Drain Stainless', 'Stainless Floor Drain', 'plumbing', 'fitting', 'buah', ARRAY['floor drain', 'saringan lantai'], 'floor drain stainless 10x10', 85000),
('MAT120', 'Closet Duduk', 'Toilet Bowl', 'plumbing', 'sanitary', 'set', ARRAY['WC', 'toilet', 'closet', 'kloset'], 'closet duduk toto', 1800000),
('MAT121', 'Wastafel', 'Wash Basin', 'plumbing', 'sanitary', 'buah', ARRAY['wastafel', 'basin', 'sink'], 'wastafel toto', 650000),
('MAT122', 'Jet Shower', 'Bidet Spray', 'plumbing', 'fitting', 'buah', ARRAY['jet shower', 'bidet', 'cebok'], 'jet shower stainless', 150000),
('MAT123', 'Water Heater 30L', 'Water Heater 30L', 'plumbing', 'appliance', 'buah', ARRAY['water heater', 'pemanas air'], 'water heater ariston 30L', 2500000),
('MAT124', 'Septic Tank 1000L', 'Septic Tank 1000L', 'plumbing', 'septic', 'buah', ARRAY['septic tank', 'septictank'], 'septic tank biotech 1000L', 3500000),
('MAT125', 'Pompa Air Jet Pump', 'Jet Pump', 'plumbing', 'pump', 'buah', ARRAY['pompa', 'jet pump', 'pump'], 'pompa air shimizu jet pump', 1200000),
('MAT126', 'Tandon Air 1000L', 'Water Tank 1000L', 'plumbing', 'tank', 'buah', ARRAY['tandon', 'toren', 'tank'], 'tandon air penguin 1000L', 1500000),
('MAT127', 'Shower Set Rain', 'Rain Shower Set', 'plumbing', 'fitting', 'set', ARRAY['shower', 'rain shower'], 'shower set rain 30cm', 850000),

-- ============================================
-- FINISHING & PAINT (MAT136-MAT155)
-- ============================================

('MAT136', 'Cat Tembok Interior', 'Interior Wall Paint', 'finishing', 'paint', 'kaleng', ARRAY['cat', 'paint', 'cat tembok'], 'cat tembok dulux 5kg', 250000),
('MAT137', 'Cat Tembok Exterior', 'Exterior Wall Paint', 'finishing', 'paint', 'kaleng', ARRAY['cat exterior', 'cat luar'], 'cat tembok exterior 5kg', 320000),
('MAT138', 'Cat Dasar Alkali', 'Alkali Primer', 'finishing', 'primer', 'kaleng', ARRAY['cat dasar', 'primer', 'alkali'], 'cat dasar alkali 5kg', 180000),
('MAT139', 'Plamir Tembok', 'Wall Putty', 'finishing', 'putty', 'kg', ARRAY['plamir', 'dempul', 'putty'], 'plamir tembok 25kg', 120000),
('MAT140', 'Cat Kayu Politur', 'Wood Varnish', 'finishing', 'paint', 'kaleng', ARRAY['politur', 'vernis', 'varnish'], 'politur kayu impra', 85000),
('MAT141', 'Cat Besi', 'Metal Paint', 'finishing', 'paint', 'kaleng', ARRAY['cat besi', 'metal paint'], 'cat besi avian', 95000),
('MAT142', 'Waterproofing Membrane', 'Waterproofing Membrane', 'finishing', 'waterproof', 'kg', ARRAY['waterproofing', 'anti bocor'], 'waterproofing aquaproof', 180000),
('MAT143', 'Epoxy Lantai', 'Epoxy Floor Coating', 'finishing', 'coating', 'kg', ARRAY['epoxy', 'coating lantai'], 'epoxy lantai 2 komponen', 250000),
('MAT144', 'Tekstur Dinding', 'Wall Texture', 'finishing', 'texture', 'kg', ARRAY['tekstur', 'texture', 'dekoratif'], 'tekstur dinding pasir', 150000),
('MAT145', 'Gypsum Board 9mm', 'Gypsum Board 9mm', 'finishing', 'ceiling', 'lembar', ARRAY['gypsum', 'gipsum', 'plafon'], 'gypsum jayaboard 9mm', 75000),
('MAT146', 'Gypsum Board 12mm', 'Gypsum Board 12mm', 'finishing', 'ceiling', 'lembar', ARRAY['gypsum 12mm'], 'gypsum jayaboard 12mm', 95000),
('MAT147', 'Rangka Hollow Plafon', 'Ceiling Frame Hollow', 'finishing', 'ceiling', 'batang', ARRAY['hollow plafon', 'rangka'], 'hollow galvanis plafon', 45000),
('MAT148', 'List Gypsum', 'Gypsum Cornice', 'finishing', 'ceiling', 'batang', ARRAY['list', 'cornice', 'profil'], 'list gypsum profil 10cm', 35000),
('MAT149', 'Acian Semen', 'Cement Render', 'finishing', 'render', 'sak', ARRAY['acian', 'render', 'plester halus'], 'acian semen 40kg', 45000),

-- ============================================
-- ROOFING (MAT156-MAT170)
-- ============================================

('MAT156', 'Genteng Beton Flat', 'Flat Concrete Roof Tile', 'roofing', 'tile', 'buah', ARRAY['genteng', 'roof tile', 'genteng beton'], 'genteng beton flat', 12000),
('MAT157', 'Genteng Keramik', 'Ceramic Roof Tile', 'roofing', 'tile', 'buah', ARRAY['genteng keramik', 'ceramic tile'], 'genteng keramik kanmuri', 18000),
('MAT158', 'Genteng Metal Pasir', 'Stone Coated Metal Tile', 'roofing', 'metal', 'lembar', ARRAY['genteng metal', 'metal roof'], 'genteng metal pasir', 85000),
('MAT159', 'Atap Spandek', 'Spandek Roofing', 'roofing', 'metal', 'lembar', ARRAY['spandek', 'spandeck'], 'atap spandek 0.3mm', 65000),
('MAT160', 'Atap Galvalum', 'Galvalume Roofing', 'roofing', 'metal', 'lembar', ARRAY['galvalum', 'galvalume'], 'atap galvalum 0.4mm', 85000),
('MAT161', 'Atap Polycarbonate', 'Polycarbonate Roofing', 'roofing', 'plastic', 'lembar', ARRAY['polycarbonate', 'polycarb', 'atap bening'], 'polycarbonate 6mm', 180000),
('MAT162', 'Nok Genteng', 'Ridge Tile', 'roofing', 'accessory', 'buah', ARRAY['nok', 'ridge', 'bubungan'], 'nok genteng beton', 25000),
('MAT163', 'Talang PVC', 'PVC Gutter', 'roofing', 'gutter', 'batang', ARRAY['talang', 'gutter', 'saluran air'], 'talang PVC 4 inch', 75000),
('MAT164', 'Flashing Aluminium', 'Aluminium Flashing', 'roofing', 'accessory', 'meter', ARRAY['flashing', 'penutup', 'aluminium'], 'flashing aluminium', 35000),
('MAT165', 'Waterproofing Atap', 'Roof Waterproofing', 'roofing', 'coating', 'kg', ARRAY['waterproof atap', 'coating atap'], 'waterproofing atap dak', 120000),

-- ============================================
-- POOL SPECIFIC (MAT171-MAT185)
-- ============================================

('MAT171', 'Mozaik Kolam Renang', 'Pool Mosaic Tile', 'pool', 'tile', 'm²', ARRAY['mozaik kolam', 'pool tile', 'kolam renang'], 'mozaik kolam renang biru', 280000),
('MAT172', 'Waterproofing Kolam', 'Pool Waterproofing', 'pool', 'waterproof', 'kg', ARRAY['waterproof kolam', 'pool coating'], 'waterproofing kolam renang', 250000),
('MAT173', 'Pipa Pool 2"', 'Pool Pipe 2"', 'pool', 'plumbing', 'batang', ARRAY['pipa kolam', 'pool pipe'], 'pipa PVC pool 2 inch', 55000),
('MAT174', 'Main Drain Pool', 'Pool Main Drain', 'pool', 'fitting', 'buah', ARRAY['main drain', 'drain kolam'], 'main drain kolam renang', 450000),
('MAT175', 'Wall Inlet Pool', 'Pool Wall Inlet', 'pool', 'fitting', 'buah', ARRAY['wall inlet', 'inlet kolam'], 'wall inlet kolam', 250000),
('MAT176', 'Skimmer Box', 'Pool Skimmer', 'pool', 'fitting', 'buah', ARRAY['skimmer', 'saringan kolam'], 'skimmer box emaux', 850000),
('MAT177', 'Pompa Kolam 1HP', 'Pool Pump 1HP', 'pool', 'equipment', 'buah', ARRAY['pompa kolam', 'pool pump'], 'pompa kolam hayward 1HP', 4500000),
('MAT178', 'Filter Kolam Sand', 'Sand Filter Pool', 'pool', 'equipment', 'buah', ARRAY['filter kolam', 'sand filter'], 'sand filter emaux 20 inch', 5500000),
('MAT179', 'Lampu Kolam LED', 'Pool LED Light', 'pool', 'lighting', 'buah', ARRAY['lampu kolam', 'pool light'], 'lampu LED kolam 12V', 850000),
('MAT180', 'Pool Ladder', 'Pool Ladder', 'pool', 'accessory', 'buah', ARRAY['tangga kolam', 'ladder'], 'tangga kolam stainless', 1200000),
('MAT181', 'Overflow Grating', 'Pool Overflow Grating', 'pool', 'fitting', 'meter', ARRAY['overflow', 'grating', 'saluran'], 'grating overflow 25cm', 180000),
('MAT182', 'Pool Coping Stone', 'Pool Edge Coping', 'pool', 'stone', 'meter', ARRAY['coping', 'pool edge', 'pinggir kolam'], 'coping batu alam kolam', 350000),
('MAT183', 'Pool Chemical Chlorine', 'Pool Chlorine', 'pool', 'chemical', 'kg', ARRAY['kaporit', 'chlorine', 'klorin'], 'kaporit kolam 1kg', 45000),

-- ============================================
-- HARDWARE & MISCELLANEOUS (MAT186-MAT200)
-- ============================================

('MAT186', 'Sealant Silikon', 'Silicone Sealant', 'hardware', 'sealant', 'tube', ARRAY['sealant', 'silikon', 'lem'], 'sealant silikon dow corning', 55000),
('MAT187', 'Lem Batu', 'Stone Adhesive', 'hardware', 'adhesive', 'kg', ARRAY['lem batu', 'stone glue'], 'lem batu alam 5kg', 85000),
('MAT188', 'Semen Nat', 'Tile Grout', 'hardware', 'grout', 'kg', ARRAY['nat', 'grout', 'semen nat'], 'semen nat weber 1kg', 35000),
('MAT189', 'Lem Keramik', 'Tile Adhesive', 'hardware', 'adhesive', 'sak', ARRAY['lem keramik', 'tile adhesive'], 'lem keramik MU 25kg', 75000),
('MAT190', 'Paku 2 inch', 'Nail 2 inch', 'hardware', 'fastener', 'kg', ARRAY['paku', 'nail'], 'paku beton 2 inch', 25000),
('MAT191', 'Skrup Gypsum', 'Gypsum Screw', 'hardware', 'fastener', 'box', ARRAY['skrup', 'sekrup', 'screw'], 'skrup gypsum 1 inch', 35000),
('MAT192', 'Dynabolt 10mm', 'Expansion Bolt 10mm', 'hardware', 'fastener', 'buah', ARRAY['dynabolt', 'fisher', 'angkur'], 'dynabolt 10mm', 8000),
('MAT193', 'Engsel Pintu', 'Door Hinge', 'hardware', 'hardware', 'pasang', ARRAY['engsel', 'hinge'], 'engsel pintu stainless 4 inch', 45000),
('MAT194', 'Handle Pintu', 'Door Handle', 'hardware', 'hardware', 'set', ARRAY['handle', 'gagang pintu'], 'handle pintu lever', 250000),
('MAT195', 'Kunci Pintu', 'Door Lock', 'hardware', 'hardware', 'set', ARRAY['kunci', 'lock'], 'kunci pintu yale', 350000),
('MAT196', 'Railing Stainless', 'Stainless Railing', 'hardware', 'railing', 'meter', ARRAY['railing', 'pegangan', 'handrail'], 'railing tangga stainless', 450000),
('MAT197', 'Teralis Besi', 'Iron Grill', 'hardware', 'grill', 'm²', ARRAY['teralis', 'grill', 'tralis'], 'teralis besi minimalis', 350000),
('MAT198', 'Pintu UPVC', 'UPVC Door', 'hardware', 'door', 'unit', ARRAY['pintu UPVC', 'UPVC door'], 'pintu UPVC 80x210', 1800000),
('MAT199', 'Jendela Aluminium', 'Aluminium Window', 'hardware', 'window', 'm²', ARRAY['jendela', 'window', 'aluminium'], 'jendela aluminium sliding', 650000),
('MAT200', 'Kaca 5mm', 'Glass 5mm', 'hardware', 'glass', 'm²', ARRAY['kaca', 'glass'], 'kaca bening 5mm', 120000);


-- ============================================
-- VERIFICATION
-- ============================================

-- Count materials by category
-- SELECT category, COUNT(*) as count FROM materials GROUP BY category ORDER BY count DESC;

-- Total count
-- SELECT COUNT(*) as total_materials FROM materials;

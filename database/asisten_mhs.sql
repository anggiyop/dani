/*
 Navicat Premium Dump SQL

 Source Server         : dhani
 Source Server Type    : MySQL
 Source Server Version : 100432 (10.4.32-MariaDB)
 Source Host           : localhost:3306
 Source Schema         : asisten_mhs

 Target Server Type    : MySQL
 Target Server Version : 100432 (10.4.32-MariaDB)
 File Encoding         : 65001

 Date: 10/12/2025 14:02:20
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for dokumen_chunk
-- ----------------------------
DROP TABLE IF EXISTS `dokumen_chunk`;
CREATE TABLE `dokumen_chunk`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `dokumen_id` int NOT NULL,
  `sop_id` int NULL DEFAULT NULL,
  `no_urut` int NOT NULL,
  `isi_chunk` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `halaman` int NULL DEFAULT NULL,
  `bagian` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_dokumen_chunk_dokumen`(`dokumen_id` ASC) USING BTREE,
  INDEX `idx_dokumen_chunk_sop`(`sop_id` ASC) USING BTREE,
  INDEX `idx_dokumen_chunk_bagian`(`bagian` ASC) USING BTREE,
  INDEX `idx_chunk_dokumen_urut`(`dokumen_id` ASC, `no_urut` ASC) USING BTREE,
  INDEX `idx_chunk_sop_urut`(`sop_id` ASC, `no_urut` ASC) USING BTREE,
  FULLTEXT INDEX `ft_chunk_isi`(`isi_chunk`),
  CONSTRAINT `fk_chunk_dokumen_kb` FOREIGN KEY (`dokumen_id`) REFERENCES `dokumen_kb` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_chunk_sop` FOREIGN KEY (`sop_id`) REFERENCES `sop` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE = InnoDB AUTO_INCREMENT = 350 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for dokumen_kb
-- ----------------------------
DROP TABLE IF EXISTS `dokumen_kb`;
CREATE TABLE `dokumen_kb`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `nama_dokumen` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `kategori` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `sumber` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `file_path` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `status_indexing` enum('belum','proses','sukses','gagal') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'belum',
  `catatan` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_dokumen_kb_kategori`(`kategori` ASC) USING BTREE,
  INDEX `idx_dokumen_kb_status`(`status_indexing` ASC) USING BTREE,
  INDEX `idx_dokumen_kb_nama`(`nama_dokumen` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for dosen
-- ----------------------------
DROP TABLE IF EXISTS `dosen`;
CREATE TABLE `dosen`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `nama_dosen` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `nip` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `nidn` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `email` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `alamat_kantor` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `link_dosen` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_dosen_nip`(`nip` ASC) USING BTREE,
  INDEX `idx_dosen_nidn`(`nidn` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1672 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for dosen_prodi
-- ----------------------------
DROP TABLE IF EXISTS `dosen_prodi`;
CREATE TABLE `dosen_prodi`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `dosen_id` int NOT NULL,
  `prodi_id` int NOT NULL,
  `is_homebase` tinyint(1) NOT NULL DEFAULT 0,
  `jabatan` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uniq_dosen_prodi`(`dosen_id` ASC, `prodi_id` ASC) USING BTREE,
  INDEX `fk_dp_prodi`(`prodi_id` ASC) USING BTREE,
  INDEX `idx_dp_dosen_homebase`(`dosen_id` ASC, `is_homebase` ASC) USING BTREE,
  CONSTRAINT `fk_dp_dosen` FOREIGN KEY (`dosen_id`) REFERENCES `dosen` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_dp_prodi` FOREIGN KEY (`prodi_id`) REFERENCES `prodi` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE = InnoDB AUTO_INCREMENT = 2559 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for fakultas
-- ----------------------------
DROP TABLE IF EXISTS `fakultas`;
CREATE TABLE `fakultas`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `kode_fakultas` varchar(2) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `nama_fakultas` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `singkatan` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `lokasi` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `website` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `telepon` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `email` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `kode_fakultas`(`kode_fakultas` ASC) USING BTREE,
  UNIQUE INDEX `uniq_fakultas_nama`(`nama_fakultas` ASC) USING BTREE,
  UNIQUE INDEX `uniq_fakultas_singkatan`(`singkatan` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 48 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for faq
-- ----------------------------
DROP TABLE IF EXISTS `faq`;
CREATE TABLE `faq`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `kategori` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `segmen_pengguna` enum('Mahasiswa','Dosen','Tenaga Kependidikan','Umum') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `pertanyaan` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `jawaban` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_faq_kategori`(`kategori` ASC) USING BTREE,
  INDEX `idx_faq_segmen`(`segmen_pengguna` ASC) USING BTREE,
  FULLTEXT INDEX `ft_faq_pertanyaan_jawaban`(`pertanyaan`, `jawaban`)
) ENGINE = InnoDB AUTO_INCREMENT = 84 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for kalender_akademik
-- ----------------------------
DROP TABLE IF EXISTS `kalender_akademik`;
CREATE TABLE `kalender_akademik`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `tahun_ajaran` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `semester` enum('Ganjil','Genap','Antara','Umum') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `kategori` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `nama_agenda` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `tanggal_mulai` date NOT NULL,
  `tanggal_selesai` date NULL DEFAULT NULL,
  `keterangan` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `link` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_kalender_tahun_semester`(`tahun_ajaran` ASC, `semester` ASC) USING BTREE,
  INDEX `idx_kalender_tanggal`(`tanggal_mulai` ASC, `tanggal_selesai` ASC) USING BTREE,
  INDEX `idx_kalender_kategori`(`kategori` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 126 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for prodi
-- ----------------------------
DROP TABLE IF EXISTS `prodi`;
CREATE TABLE `prodi`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `fakultas_id` int NOT NULL,
  `nama_prodi` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `jenjang` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `akreditasi` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `lokasi` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `website` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `telepon` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `email` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uniq_prodi_nama_fakultas`(`fakultas_id` ASC, `nama_prodi` ASC, `jenjang` ASC) USING BTREE,
  CONSTRAINT `prodi_ibfk_1` FOREIGN KEY (`fakultas_id`) REFERENCES `fakultas` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE = InnoDB AUTO_INCREMENT = 180 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for sop
-- ----------------------------
DROP TABLE IF EXISTS `sop`;
CREATE TABLE `sop`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `kode_sop` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `judul_sop` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `deskripsi_singkat` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `unit_layanan_id` int NOT NULL,
  `kategori_layanan` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `sasaran_layanan` enum('Mahasiswa','Dosen','Tenaga Kependidikan','Umum/Eksternal','Campuran') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `tanggal_berlaku` date NULL DEFAULT NULL,
  `file_url` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `halaman_pdf` int NULL DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uniq_kode_sop`(`kode_sop` ASC) USING BTREE,
  INDEX `idx_sop_sasaran`(`sasaran_layanan` ASC) USING BTREE,
  INDEX `idx_sop_kategori`(`kategori_layanan` ASC) USING BTREE,
  INDEX `idx_sop_unit_sasaran`(`unit_layanan_id` ASC, `sasaran_layanan` ASC) USING BTREE,
  CONSTRAINT `fk_sop_unit_layanan` FOREIGN KEY (`unit_layanan_id`) REFERENCES `unit_layanan` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE = InnoDB AUTO_INCREMENT = 74 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for sop_komponen
-- ----------------------------
DROP TABLE IF EXISTS `sop_komponen`;
CREATE TABLE `sop_komponen`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `sop_id` int NOT NULL,
  `jenis` enum('persyaratan','sistem_prosedur','jangka_waktu','biaya','produk','pengaduan') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `judul` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `isi` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `halaman` int NULL DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_sop_komponen_sop_id`(`sop_id` ASC) USING BTREE,
  INDEX `idx_sop_komponen_jenis`(`jenis` ASC) USING BTREE,
  INDEX `idx_sop_komponen_sop_jenis`(`sop_id` ASC, `jenis` ASC) USING BTREE,
  FULLTEXT INDEX `ft_sop_komponen_isi`(`isi`),
  CONSTRAINT `fk_sop_komponen_sop` FOREIGN KEY (`sop_id`) REFERENCES `sop` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE = InnoDB AUTO_INCREMENT = 223 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for sop_step
-- ----------------------------
DROP TABLE IF EXISTS `sop_step`;
CREATE TABLE `sop_step`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `sop_id` int NOT NULL,
  `no_urut` int NOT NULL,
  `deskripsi` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `pelaksana` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `estimasi_waktu` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_sop_step_sop_urut`(`sop_id` ASC, `no_urut` ASC) USING BTREE,
  CONSTRAINT `fk_sop_step_sop` FOREIGN KEY (`sop_id`) REFERENCES `sop` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE = InnoDB AUTO_INCREMENT = 128 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for unit_layanan
-- ----------------------------
DROP TABLE IF EXISTS `unit_layanan`;
CREATE TABLE `unit_layanan`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `nama_unit` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `deskripsi` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `email_kontak` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `telepon_kontak` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `alamat` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_unit_layanan_nama`(`nama_unit` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

SET FOREIGN_KEY_CHECKS = 1;

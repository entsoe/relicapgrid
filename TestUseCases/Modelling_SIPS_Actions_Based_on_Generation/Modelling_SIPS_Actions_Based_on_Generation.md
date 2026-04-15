# Modelling SIPS Actions Based on Generation (Anti-swing Protection)

The test case should be performed as follows:

1)  Open the CGM model or [IGM Belgovia](https://github.com/entsoe/relicapgrid/tree/archive-main-do-not-use/Instance/Belgovia/Grid/cimxml).

2)  Import the list of SIPS from Remedial Action Profile ([SIPS_UC6_Anti-Swing_Belgovia.xml](https://github.com/entsoe/relicapgrid/blob/cgmes-3.0_ncp-2.4_tc-1.1/Instance/NetworkCode/Belgovia/Belgovia_instance/SIPS/SIPS_UC6_Anti-swing_Belgovia.xml)).

3)  Check if SIPS was uploaded correctly and the logic is as expected.

4)  Import the Contingency List from Contingency Profile ([Belgovia_CO_SIPS.xml](https://github.com/entsoe/relicapgrid/blob/cgmes-3.0_ncp-2.4_tc-1.1/Instance/NetworkCode/Belgovia/Belgovia_instance/Belgovia_CO_SIPS.xml)).

5)  Run contingency analysis including SIPS activation.

6)  Check if SIPS was triggered correctly:

- For exceptional contingency on BO-TR2_1 and line TieLine_SD_BO3 SIPS should set the active power on generator BO-G1 to -20MW.

Test data was prepared based on Belgovia individual grid model. The elements connected to the PP_Brussia substation were used:

![](images/media/image2.svg)

The triggering action is the disconnection of two elements: BO-TR2_1 and line TieLine_SD_BO3, which is realized by checking if the power flow in the terminals (mRID 9f5dbaf3-e384-4e86-9d49-f43c30b4e354 and 60e4a112-8b97-e4ee-69b3-ece28a25376d) to which the elements are connected is less than 1 MW.

- The action is to set the active power of the generator BO-G1 (mRID 3a3b27be-b18b-4385-b557-6735d733baf0 ) to Pmin which is 20 MW in this case.

- The SIPS model was prepared in file named: SIPS_UC6_Anti-Swing_Belgovia.xml

To force the power drop in BO-TR2_1 and line TieLine_SD_BO3 to less than 1MW, the loss of BO-TR2_1 (mRID a708c3bc-465d-4fe7-b6ef-6fa6408a62b0) and TieLine_SD_BO3 (mRID d9622e7f-5bf0-4e7e-b766-b8596c6fe4ae) is added to the contingency list ([Belgovia_CO_SIPS.xml](https://github.com/entsoe/relicapgrid/blob/cgmes-3.0_ncp-2.4_tc-1.1/Instance/NetworkCode/Belgovia/Belgovia_instance/Belgovia_CO_SIPS.xml)) as an exceptional contingency.

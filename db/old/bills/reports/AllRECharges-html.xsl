<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:fo="http://www.w3.org/1999/XSL/Format" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:fn="http://www.w3.org/2005/xpath-functions">
	<xsl:output method="html"/>
	<xsl:strip-space  elements="*"/>
	<xsl:template match="/">
        <html>
            <head>
                <style type="text/css">
                    td {padding-right: 10px; padding-left: 10px;}
                    tr:nth-child(2n+0) {background-color: gray;}
                </style>
            </head>
            <body>
                <!--p><xsl:template select="bills"/></p-->
                <span>Total: $</span><xsl:value-of select="bills/@total"/>
                <table>
                    <tr>
                        <th>Account</th>
                        <th>Addressee</th>
                        <th>Service</th>
                        <th class="">Begin</th>
                        <th class="">End</th>
                        <th>Charge</th>
                    </tr>
                    <xsl:for-each select="bills/bill">
                        <tr>
                            <xsl:apply-templates/>
                        </tr>
                    </xsl:for-each>
                </table>
            </body>
        </html>
   	</xsl:template>

    <xsl:template match="bills"><xsl:value-of select="@total"/></xsl:template>
    <xsl:template match="account"><td><xsl:value-of select="."/>-<xsl:value-of select="../billseq"/></td></xsl:template>
    <xsl:template match="billseq"></xsl:template>
	<xsl:template match="addressee">
		<xsl:choose>
			<xsl:when test=". != '' "><td><xsl:value-of select="." /></td></xsl:when>
            <xsl:otherwise><td>N/A</td></xsl:otherwise>
		</xsl:choose>
	</xsl:template>
	<xsl:template match="service"><td><xsl:value-of select="."/></td></xsl:template>
	<xsl:template match="periodbegin"><td class="periodbegin"><xsl:value-of select="."/></td></xsl:template>
	<xsl:template match="periodend"><td class="periodend"><xsl:value-of select="."/></td></xsl:template>
    <xsl:template match="charge"><td style="text-align: right;"><xsl:value-of select="."/></td></xsl:template>
</xsl:stylesheet>
